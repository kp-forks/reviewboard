"""Test cases for testing hosting services."""

from __future__ import annotations

import io
import json
from contextlib import contextmanager
from typing import Generic, TypeVar, TypedDict, TYPE_CHECKING, cast, overload
from urllib.error import HTTPError
from urllib.parse import urlparse

import kgb

from reviewboard.hostingsvcs.base import (
    BaseHostingService,
    hosting_service_registry,
)
from reviewboard.hostingsvcs.models import HostingServiceAccount
from reviewboard.testing import TestCase

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping, Sequence
    from typing import Any, Literal

    from kgb.calls import SpyCall
    from typelets.json import JSONValue
    from typing_extensions import NotRequired, TypeAlias

    from reviewboard.hostingsvcs.base.client import HostingServiceClient
    from reviewboard.hostingsvcs.base.forms import (
        BaseHostingServiceRepositoryForm,
    )
    from reviewboard.hostingsvcs.base.hosting_service import (
        HostingServiceCredentials,
        RepositoryFields,
    )
    from reviewboard.hostingsvcs.base.http import (
        HostingServiceHTTPRequest,
        HostingServiceHTTPResponse,
        HTTPHeaders,
    )
    from reviewboard.scmtools.models import Repository
    from reviewboard.site.models import LocalSite

    HttpRequestMethod: TypeAlias = Callable[
        [HostingServiceClient, HostingServiceHTTPRequest],
        HostingServiceHTTPResponse
    ]


#: Type variable for the hosting service.
#:
#: Version Added:
#:     7.1
_THostingService = TypeVar('_THostingService', bound=BaseHostingService)


class HttpTestContext(Generic[_THostingService]):
    """State and functions for an HTTP test.

    This is provided when calling
    :py:meth:`HostingServiceTestCase.setup_http_test`. It serves up state
    that can be tested with, along with useful functions for creating necessary
    objects and asserting results.

    Version Added:
        3.0.4

    Attributes:
        client (reviewboard.hostingsvcs.base.ciient.HostingServiceClient):
            The hosting service client used to perform HTTP requests for
            this test.

        hosting_account (reviewboard.hostingsvcs.models.HostingServiceAccount):
            The hosting account used for the test.

        service (reviewboard.hostingsvcs.base.hosting_service.
                 BaseHostingService):
            The hosting service instance used for the test.
    """

    ######################
    # Instance variables #
    ######################

    #: The hosting service instance.
    service: _THostingService

    def __init__(
        self,
        test_case: HostingServiceTestCase[_THostingService],
        hosting_account: HostingServiceAccount,
        http_request_func: HttpRequestMethod,
    ) -> None:
        """Initialize the test context.

        Args:
            test_case (HostingServiceTestCase):
                The parent test case.

            hosting_account (reviewboard.hostingsvcs.models.
                             HostingServiceAccount):
                The hosting service account set up for the test.

            http_request_func (callable):
                The function used to handle HTTP requests.
        """
        self.hosting_account = hosting_account
        self.service = cast(_THostingService, hosting_account.service)
        self.client = self.service.client

        self.http_requests = []
        self.http_credentials = []

        self._test_case = test_case
        self._http_request_func = http_request_func

    @property
    def http_calls(self) -> Sequence[SpyCall]:
        """The HTTP calls made by the service.

        This is a list of spy calls from KGB.
        """
        return self._http_request_func.calls  # type:ignore

    def create_repository(
        self,
        **kwargs,
    ) -> Repository:
        """Create a repository using the current hosting account.

        This wraps :py:meth:`HostingServiceTestCase.create_repository`,
        specifying the hosting account that was set up in this test context.

        Args:
            **kwargs (dict):
                Keyword arguments to pass to
                :py:meth:`HostingServiceTestCase.create_repository`.

        Returns:
            reviewboard.scmtools.models.Repository:
            The new repository.
        """
        return self._test_case.create_repository(
            hosting_account=self.hosting_account,
            **kwargs)

    def assertHTTPCall(
        self,
        index: int = 0,
        url: str = '',
        method: str = 'GET',
        body: (bytes | None) = None,
        headers: (HTTPHeaders | None) = None,
        **kwargs,
    ) -> None:
        """Assert that an HTTP call was made.

        This sets some defaults based on the test case, helping both to
        eliminate the amount of data that needs to be checked and helping
        avoid missed data.

        Any keyword argument accepted by
        :py:meth:`HostingServiceClient.http_request()
        <reviewboard.hostingsvcs.base.client.HostingServiceClient.
        http_request>` can be provided.

        If ``username`` or ``password`` are not explicitly provided, the
        values from :py:attr:`HostingServiceTestCase.default_username` or
        :py:attr:`HostingServiceTestCase.default_password` will be used.

        Args:
            index (int, optional):
                The index of the HTTP call.

            url (str, optional):
                The URL being accessed.

            method (str, optional);
                The HTTP method expected for the call.

            body (bytes, optional):
                The expected body for the call (used for POST/PUT requests).

            headers (dict, optional):
                The expected headers for the call.

            **kwargs (dict):
                Additional parameters to check in the call.
        """
        failureException = self._test_case.failureException

        # Check arguments against the request.
        request = self.http_requests[index]

        if url and request.url != url:
            raise failureException(
                f'HTTP call {index}: URL: {request.url!r} != {url!r}'
            )

        if request.method != method:
            raise failureException(
                f'HTTP call {index}: method: {request.method!r} != {method!r}'
            )

        if request.body != body:
            raise failureException(
                f'HTTP call {index}: body: {request.body!r} != {body!r}'
            )

        # Check arguments against the generated credentials.
        if 'username' in kwargs and 'password' in kwargs:
            # This is a simplification for checking standard username/password
            # credentials, and maintains backwards-compatibility.
            username = kwargs.pop('username')
            password = kwargs.pop('password')

            if username is None and password is None:
                credentials = {}
            else:
                credentials = {
                    'username': username,
                    'password': password,
                }
        else:
            credentials = kwargs.pop('credentials',
                                     self._test_case.default_http_credentials)

        if self.http_credentials[index] != credentials:
            raise failureException(
                f'HTTP call {index}: credentials: '
                f'{self.http_credentials[index]!r} != {credentials!r}'
            )

        # Check arguments against the call.
        call = self.http_calls[index]

        if call.kwargs['headers'] != headers:
            raise failureException(
                f'HTTP call {index}: headers: {call.kwargs["headers"]!r} != '
                f'{headers!r}'
            )

        for key, value in kwargs.items():
            if call.kwargs[key] != value:
                raise failureException(
                    f'HTTP call {index}: {key!r}: {call.kwargs[key]!r} != '
                    f'{value!r}'
                )


class HttpTestPath(TypedDict):
    """Data for a test path provided to the hosting service test case.

    Version Added:
        7.1
    """

    #: The headers to return with the response.
    headers: NotRequired[HTTPHeaders | None]

    #: The payload to return in the response.
    payload: NotRequired[bytes | None]

    #: The status code for the response.
    status_code: NotRequired[int | None]


class HostingServiceTestCase(kgb.SpyAgency,
                             TestCase,
                             Generic[_THostingService]):
    """Base class for unit tests for hosting services."""

    #: The hosting service class.
    service_class: type[_THostingService]

    #: The registered name of the service.
    service_name = None

    #: The default username to use for accounts.
    default_username = 'myuser'

    #: The default password to use for accounts.
    default_password = 'mypass'

    #: The default hosting URL to use for accounts.
    #:
    #: This is only used for accounts set with ``use_url=True`` (or when
    #: ``default_use_hosting_url`` is ``True``).
    default_hosting_url = 'https://example.com'

    #: Whether to create accounts attached to a hosting URL by default.
    default_use_hosting_url = False

    #: Default data to set for created hosting service accounts.
    default_account_data = {}

    #: Default data to set for created repositories.
    default_repository_extra_data = {}

    #: Default SCMTool to set for created repositories.
    default_repository_tool_name = None

    fixtures = ['test_scmtools']

    @property
    def default_http_credentials(self) -> HostingServiceCredentials:
        """The default credentials sent in HTTP requests."""
        return {
            'username': self.default_username,
            'password': self.default_password,
        }

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the test case class."""
        super().setUpClass()

        assert cls.service_name is not None
        cls.service_class = cast(
            type[_THostingService],
            hosting_service_registry.get_hosting_service(cls.service_name))

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

    @contextmanager
    def setup_http_test(
        self,
        http_request_func: (HttpRequestMethod | None) = None,
        payload: (bytes | None) = None,
        headers: (HTTPHeaders | None) = None,
        status_code: (int | None) = None,
        hosting_account: (HostingServiceAccount | None) = None,
        expected_http_calls: (int | None) = None,
    ) -> Generator[HttpTestContext[_THostingService], Any, None]:
        """Set up state for HTTP-related tests.

        This takes the hard work out of testing hosting service functionality
        that needs to communicate over HTTP. It's a context manager that takes
        in information on what to return to the client and yields a context
        containing state and functions for performing and checking calls.

        By default, this will cause any HTTP requests to return an empty
        byte string as a payload. Explicit payloads can also be provided,
        as can an HTTP error code. For more advanced needs, a function can
        be provided that will handle the HTTP request (which is useful when
        your test may invoke several HTTP endpoints).

        This may be called repeatedly in the same test function.

        Args:
            http_request_func (callable, optional):
                An explicit HTTP request function to call when performing an
                HTTP request. This will override
                :py:meth:`reviewboard.hostingsvcs.base.client.
                HostingServiceClient.http_request`.

            payload (bytes, optional):
                An explicit payload to return to the client.

            headers (dict, optional):
                Headers to send along with the result.

            status_code (int, optional):
                An explicit HTTP status code. Only values >= 400 are used.
                Providing an error code will raise an HTTP error to the
                client, using the ``payload`` value if provided.

            hosting_account (reviewboard.hostingsvcs.models.
                             HostingServiceAccount, optional):
                An explicit hosting account to use. If not provided, one will
                be created using :py:meth:`create_hosting_account`.

            expected_http_calls (int, optional):
                The number of HTTP calls expected. If provided, this will
                assert that there were this many HTTP calls.

        Context:
            HttpTestContext:
            The context for the test, containing state, helper functions,
            and results.
        """
        if hosting_account is None:
            hosting_account = self.create_hosting_account()

        if http_request_func:
            # Sanity-check that the caller isn't mixing incompatible arguments.
            if payload is not None:
                raise ValueError(
                    'http_request_func and payload cannot both be provided')
            elif status_code is not None:
                raise ValueError(
                    'http_request_func and status_code cannot both be '
                    'provided')
        else:
            http_request_func = self.make_handler_for_paths({
                None: {
                    'status_code': status_code,
                    'payload': payload,
                    'headers': headers,
                },
            })

        client = hosting_account.service.client
        client_cls = type(client)

        # Reset for this next test. This allows the test case to use
        # this context function multiple times.
        for func in (client_cls.build_http_request,
                     client_cls.get_http_credentials,
                     client_cls.http_request,
                     client_cls.open_http_request):
            if hasattr(func, 'unspy'):
                self.unspy(func)

        self.spy_on(client_cls.http_request,
                    owner=client_cls)
        self.spy_on(client_cls.open_http_request,
                    owner=client_cls,
                    call_fake=http_request_func)

        ctx = HttpTestContext(
            test_case=self,
            hosting_account=hosting_account,
            http_request_func=client_cls.http_request)

        def _build_http_request(
            client: HostingServiceClient,
            *args,
            **kwargs,
        ) -> HostingServiceHTTPRequest:
            spy = self.get_spy(client.build_http_request)
            result = spy.call_original(client, *args, **kwargs)
            ctx.http_requests.append(result)

            return result

        def _get_http_credentials(
            client: HostingServiceClient,
            *args,
            **kwargs,
        ) -> HostingServiceCredentials:
            spy = self.get_spy(client.get_http_credentials)
            result = spy.call_original(client, *args, **kwargs)
            ctx.http_credentials.append(result)

            return result

        self.spy_on(client_cls.build_http_request,
                    owner=client_cls,
                    call_fake=_build_http_request)
        self.spy_on(client_cls.get_http_credentials,
                    owner=client_cls,
                    call_fake=_get_http_credentials)

        yield ctx

        if expected_http_calls is not None:
            self.assertEqual(len(ctx.http_calls), expected_http_calls)

    def make_handler_for_paths(
        self,
        paths: Mapping[str | None, HttpTestPath],
    ) -> HttpRequestMethod:
        """Return an HTTP handler function for serving the supplied paths.

        This is meant to be passed to :py:meth:`setup_http_test`.

        This takes a dictionary matching paths to information to return. Each
        key is a path relative to the domain, which may optionally contain a
        full query string to match. It may also be ``None``, which is the
        fallback.

        Each value is a dictionary containing optional ``payload``,
        ``status_code``, or ``headers`` values.

        Args:
            paths (dict):
                The dictionary of paths.

        Returns:
            callable:
            The resulting HTTP handler function.

        Example:
            .. code-block:: python

               handler = make_handler_for_paths({
                   '/api/1/diffs/': {
                       'payload': b'...',
                       'headers': {
                           str('My-Header'): str('value'),
                        },
                   },
                   '/api/1/bad/': {
                       'status_code': 404,
                       'payload': b'Not found.',
                   },
                   None: {
                       'payload': b'fallback data...',
                   },
               })
        """
        # Validate the paths to make sure payloads are in the right format.
        for _path, path_info in paths.items():
            payload = path_info.get('payload')

            if payload is not None and not isinstance(payload, bytes):
                raise TypeError('payload must be a byte string or None')

        def _handler(
            client: HostingServiceClient,
            request: HostingServiceHTTPRequest,
        ) -> HostingServiceHTTPResponse:
            url = request.url
            parts = urlparse(url)

            full_path = f'{parts.path}?{parts.query}'
            path_info = paths.get(full_path)

            if path_info is None:
                path_info = paths.get(parts.path)

                if path_info is None:
                    path_info = paths.get(None)

                    if path_info is None:
                        self.fail(f'Unexpected path "{full_path}"')

            status_code = path_info.get('status_code') or 200
            payload = path_info.get('payload') or b''
            headers = path_info.get('headers') or {}

            if status_code >= 400:
                raise HTTPError(
                    url=url,
                    code=status_code,
                    msg='',
                    hdrs=headers,  # type:ignore
                    fp=io.BytesIO(payload))
            else:
                http_response_cls = \
                    self.service_class.client_class.http_response_cls

                return http_response_cls(
                    request=request,
                    url=url,
                    data=payload,
                    headers=headers,
                    status_code=status_code)

        return _handler

    @overload
    def dump_json(
        self,
        data: JSONValue,
        for_response: Literal[False],
    ) -> str:
        ...

    @overload
    def dump_json(
        self,
        data: JSONValue,
        for_response: Literal[True] = True,
    ) -> bytes:
        ...

    def dump_json(
        self,
        data: JSONValue,
        for_response: bool = True,
    ) -> bytes | str:
        """Dump JSON-compatible data to the proper string type.

        If ``for_response`` is ``True`` (the default), the resulting string
        will be a byte string. Otherwise, it will be a Unicode string.

        Args:
            data (object):
                The data to dump.

            for_response (bool, optional):
                Whether the resulting string is intended for a response
                payload.

        Returns:
            str or bytes:
            The serialized string.
        """
        result = json.dumps(data)

        if for_response and isinstance(result, str):
            result = result.encode('utf-8')

        return result

    def get_form(
        self,
        plan: (str | None) = None,
        fields: (dict[str, Any] | None) = None,
        repository: (Repository | None) = None,
    ) -> BaseHostingServiceRepositoryForm:
        """Return the configuration form for the hosting service.

        Args:
            plan (str, optional):
                The hosting plan that the configuration form is for.

            fields (dict, optional):
                The initial field data to populate the form with.

            repository (reviewboard.scmtools.models.Repository, optional):
                A specific repository the form will load from and save to.

        Returns:
            reviewboard.hostingsvcs.base.forms.
            BaseHostingServiceRepositoryForm:
            The resulting hosting service form.
        """
        assert self.service_class is not None
        form_cls = self.service_class.get_field(name='form', plan=plan)

        self.assertIsNotNone(form_cls)

        form = form_cls(data=fields or {},
                        repository=repository,
                        hosting_service_cls=self.service_class)
        self.assertTrue(form.is_valid())

        return form

    def create_hosting_account(
        self,
        use_url: (bool | None) = None,
        local_site: (LocalSite | None) = None,
        data: (dict[str, Any] | None) = None,
    ) -> HostingServiceAccount:
        """Create a hosting account to test with.

        Args:
            use_url (bool, optional):
                Whether the account should be attached to a given hosting URL,
                for self-hosted services. If set, this will use
                ``https://example.com``.

            local_site (reviewboard.site.models.LocalSite, optional):
                A Local Site to attach the account to.

            data (dict, optional):
                Optional data to set for the account. If this is ``None``,
                :py:attr:`default_account_data` will be used.

        Returns:
            reviewboard.hostingsvcs.models.HostingServiceAccount:
            The new hosting service account.
        """
        if use_url is None:
            use_url = self.default_use_hosting_url

        if use_url:
            hosting_url = self.default_hosting_url
        else:
            hosting_url = None

        account = HostingServiceAccount(service_name=self.service_name,
                                        username=self.default_username,
                                        hosting_url=hosting_url,
                                        local_site=local_site)

        if data is not None:
            account.data = data
        else:
            account.data = self.default_account_data

        account.save()

        return account

    def create_repository(
        self,
        **kwargs,
    ) -> Repository:
        """Create a repository for a test.

        This wraps :py:meth:`TestCase.create_repository()
        <reviewboard.testing.testcase.TestCase.create_repository>`,
        specifying a default SCM Tool name (if
        :py:attr:`default_repository_tool_name`) is set) and
        extra data (if :py:attr:`default_repository_extra_data` is set).

        Args:
            **kwargs (dict):
                Keyword arguments to pass to
                :py:meth:`TestCase.create_repository()
                <reviewboard.testing.testcase.TestCase.create_repository>`.

        Returns:
            reviewboard.scmtools.models.Repository:
            The new repository.
        """
        if 'extra_data' not in kwargs:
            kwargs['extra_data'] = self.default_repository_extra_data.copy()

        return super().create_repository(**kwargs)

    def get_repository_fields(
        self,
        tool_name: str,
        fields: dict[str, Any],
        plan: (str | None) = None,
        with_url: (bool | None) = None,
        hosting_account: (HostingServiceAccount | None) = None,
    ) -> RepositoryFields:
        """Return populated fields for a repository.

        Args:
            tool_name (str):
                The name of the SCM Tool used for the repository.

            fields (dict):
                A dictionary of fields for the hosting service form.

            plan (str, optional):
                The optional hosting plan to use for the configuration.

            with_url (bool, optional):
                Whether the account should be attached to a given hosting URL,
                for self-hosted services. If set, this will use
                ``https://example.com``. This is ignored if ``hosting_account``
                is provided.

                This value defaults to :py:attr:`default_use_hosting_url`

            hosting_account (reviewboard.hostingsvcs.models.
                             HostingServiceAccount, optional):
                An explicit hosting service account to use.

        Returns:
            dict:
            The populated field data for the repository.
        """
        form = self.get_form(plan, fields)

        if not hosting_account:
            hosting_account = self.create_hosting_account(with_url)

        service = hosting_account.service
        self.assertIsNotNone(service)

        cleaned_data = form.clean()
        assert cleaned_data is not None

        field_vars = cleaned_data.copy()
        field_vars.update(hosting_account.data)

        return service.get_repository_fields(
            username=hosting_account.username,
            hosting_url=self.default_hosting_url,
            plan=plan,
            tool_name=tool_name,
            field_vars=field_vars)
