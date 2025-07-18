"""Definitions for the StatusUpdate model."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _
from djblets.db.fields import JSONField

from reviewboard.changedescs.models import ChangeDescription
from reviewboard.integrations.models import IntegrationConfig
from reviewboard.reviews.managers import StatusUpdateManager
from reviewboard.reviews.models.base_comment import BaseComment
from reviewboard.reviews.models.review import Review
from reviewboard.reviews.models.review_request import ReviewRequest
from reviewboard.reviews.signals import status_update_request_run
from reviewboard.site.models import LocalSite

if TYPE_CHECKING:
    from typing import ClassVar, Literal, Optional

    from django.contrib.auth.models import AnonymousUser
    from djblets.util.typing import StrOrPromise
    from typing_extensions import TypeAlias

    _StateFlag: TypeAlias = Literal['C', 'E', 'F', 'P', 'R', 'S', 'T']
    _StateStr: TypeAlias = Literal[
        'cancelled',
        'done-failure',
        'done-success',
        'error',
        'not-yet-run',
        'pending',
        'timed-out',
    ]


class StatusUpdate(models.Model):
    """A status update from a third-party service or extension.

    This status model allows external services (such as continuous integration
    services, Review Bot, etc.) to provide an update on their status. An
    example of this would be a CI tool which does experimental builds of
    changes. While the build is running, that tool would set its status to
    pending, and when it was done, would set it to one of the done states,
    and potentially associate it with a review containing issues.
    """

    #: The pending state.
    PENDING = 'P'

    #: The completed successfully state.
    DONE_SUCCESS = 'S'

    #: The completed with reported failures state.
    DONE_FAILURE = 'F'

    #: The error state.
    ERROR = 'E'

    #: Timeout state.
    TIMEOUT = 'T'

    #: Not yet run state.
    NOT_YET_RUN = 'R'

    #: Cancelled state.
    CANCELLED = 'C'

    STATUSES = (
        (PENDING, _('Pending')),
        (DONE_SUCCESS, _('Done (Success)')),
        (DONE_FAILURE, _('Done (Failure)')),
        (ERROR, _('Error')),
        (TIMEOUT, _('Timed Out')),
        (NOT_YET_RUN, _('Not Yet Run')),
        (CANCELLED, _('Cancelled')),
    )

    _INTEGRATION_CONFIG_KEY = '__integration_config_id'

    #: An identifier for the service posting this status update.
    #:
    #: This ID is self-assigned, and just needs to be unique to that service.
    #: Possible values can be an extension ID, webhook URL, or a script name.
    service_id = models.CharField(_('Service ID'), max_length=255)

    #: The user who created this status update.
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='status_updates',
        verbose_name=_('User'),
        blank=True,
        null=True)

    #: The timestamp of the status update.
    timestamp = models.DateTimeField(_('Timestamp'), auto_now=True)

    #: A user-visible short summary of the status update.
    #:
    #: This is typically the name of the integration or tool that was run.
    summary = models.CharField(_('Summary'), max_length=255)

    #: A user-visible description on the status update.
    #:
    #: This is shown in the UI adjacent to the summary. Typical results might
    #: be things like "running." or "failed.". This should include punctuation.
    description = models.CharField(_('Description'), max_length=255,
                                   blank=True)

    #: An optional link.
    #:
    #: This is used in case the tool has some external page, such as a build
    #: results page on a CI system.
    url = models.URLField(_('Link URL'), max_length=255, blank=True)

    #: Text for the link. If ``url`` is empty, this will not be used.
    url_text = models.CharField(_('Link text'), max_length=64, blank=True)

    #: The current state of this status update.
    #:
    #: This should be set to :py:attr:`PENDING` while the service is
    #: processing the update, and then to either :py:attr:`DONE_SUCCESS` or
    #: :py:attr:`DONE_FAILURE` once complete. If the service encountered some
    #: error which prevented completion, this should be set to
    #: :py:attr:`ERROR`.
    state = models.CharField(_('State'), max_length=1, choices=STATUSES)

    #: The review request that this status update is for.
    review_request = models.ForeignKey(
        ReviewRequest,
        on_delete=models.CASCADE,
        related_name='status_updates',
        verbose_name=_('Review Request'))

    #: The change to the review request that this status update is for.
    #:
    #: If this is ``None``, this status update refers to the review request as
    #: a whole (for example, the initial diff that was posted).
    change_description = models.ForeignKey(
        ChangeDescription,
        on_delete=models.CASCADE,
        related_name='status_updates',
        verbose_name=_('Change Description'),
        null=True,
        blank=True)

    #: An optional review created for this status update.
    #:
    #: This allows the third-party service to create comments and open issues.
    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name='status_update',
        verbose_name=_('Review'),
        null=True,
        blank=True)

    #: Any extra data that the service wants to store for this status update.
    extra_data = JSONField(null=True)

    #: An (optional) timeout, in seconds. If this is non-None and the state has
    #: been ``PENDING`` for longer than this period (computed from the
    #: :py:attr:`timestamp` field), :py:attr:`effective_state` will be
    #: ``TIMEOUT``.
    timeout = models.IntegerField(null=True, blank=True)

    objects: ClassVar[StatusUpdateManager] = StatusUpdateManager()

    ######################
    # Instance variables #
    ######################

    _integration_config: Optional[IntegrationConfig]

    @staticmethod
    def state_to_string(
        state: _StateFlag,
    ) -> _StateStr:
        """Return a string representation of a status update state.

        Args:
            state (str):
                A single-character string representing the state.

        Returns:
            str:
            A longer string representation of the state suitable for use in
            the API.
        """
        if state == StatusUpdate.PENDING:
            return 'pending'
        elif state == StatusUpdate.DONE_SUCCESS:
            return 'done-success'
        elif state == StatusUpdate.DONE_FAILURE:
            return 'done-failure'
        elif state == StatusUpdate.ERROR:
            return 'error'
        elif state == StatusUpdate.TIMEOUT:
            return 'timed-out'
        elif state == StatusUpdate.NOT_YET_RUN:
            return 'not-yet-run'
        elif state == StatusUpdate.CANCELLED:
            return 'cancelled'
        else:
            raise ValueError(f'Invalid state "{state}"')  # type:ignore

    @staticmethod
    def string_to_state(
        state: _StateStr,
    ) -> _StateFlag:
        """Return a status update state from an API string.

        Args:
            state (str):
                A string from the API representing the state.

        Returns:
            str:
            A single-character string representing the state, suitable for
            storage in the ``state`` field.
        """
        if state == 'pending':
            return StatusUpdate.PENDING
        elif state == 'done-success':
            return StatusUpdate.DONE_SUCCESS
        elif state == 'done-failure':
            return StatusUpdate.DONE_FAILURE
        elif state == 'error':
            return StatusUpdate.ERROR
        elif state == 'timed-out':
            return StatusUpdate.TIMEOUT
        elif state == 'not-yet-run':
            return StatusUpdate.NOT_YET_RUN
        elif state == 'cancelled':
            return StatusUpdate.CANCELLED
        else:
            raise ValueError(f'Invalid state string "{state}"')  # type:ignore

    @property
    def integration_config(self) -> Optional[IntegrationConfig]:
        """The integration config that manages this status update, if any.

        If the stored configuration no longer exists, or is no longer
        applicable to any associated :term:`Local Site`, then this will be
        ``None``.

        The configuration is cached for repeated lookups.

        Version Added:
            5.0.3

        Type:
            reviewboard.integrations.models.IntegrationConfig
        """
        config: Optional[IntegrationConfig]

        if hasattr(self, '_integration_config'):
            config = self._integration_config
        else:
            config = None
            config_id = self.extra_data.get(self._INTEGRATION_CONFIG_KEY)

            if config_id:
                try:
                    config = (
                        IntegrationConfig.objects
                        .get(Q(pk=config_id) &
                             LocalSite.objects.build_q(
                                 self.review_request.local_site_id,
                                 allow_all=False))
                    )
                except IntegrationConfig.DoesNotExist:
                    # Either the configuration was removed, or it's on the
                    # wrong Local Site. Fall back to None.
                    pass

            self._integration_config = config

        return config

    @integration_config.setter
    def integration_config(
        self,
        config: IntegrationConfig | None,
    ) -> None:
        """Set the integration configuration for this status update.

        This allows integrations to properly use the correct configuration
        when manually running for the status update.

        Version Added:
            5.0.3

        Args:
            config (reviewboard.integrations.models.IntegrationConfig):
                The configuration to store.

                The configuration's :term:`Local Site` must match that of
                the status update.

        Raises:
            ValueError:
                The provided configuration value is not supported by this
                status update.
        """
        if config:
            if config.local_site_id != self.review_request.local_site_id:
                raise ValueError(
                    'The integration configuration and Status Update must '
                    'have the same Local Site.')

            self.extra_data[self._INTEGRATION_CONFIG_KEY] = config.pk
        else:
            self.extra_data.pop(self._INTEGRATION_CONFIG_KEY, None)

        self._integration_config = config

    def is_mutable_by(
        self,
        user: User | AnonymousUser,
    ) -> bool:
        """Return whether the user can modify this status update.

        Args:
            user (django.contrib.auth.models.User):
                The user to check.

        Returns:
            bool:
            True if the user can modify this status update.
        """
        return (user.is_authenticated and
                (self.user_id == user.pk or
                 user.has_perm('reviews.change_statusupdate',
                               self.review_request.local_site)))

    @property
    def effective_state(self) -> _StateFlag:
        """The state of the status update, taking into account timeouts.

        Type:
            str
        """
        if self.state == self.PENDING and self.timeout is not None:
            timeout = self.timestamp + datetime.timedelta(seconds=self.timeout)

            if timezone.now() > timeout:
                return self.TIMEOUT

        return self.state

    def drop_open_issues(self) -> None:
        """Drop any open issues associated with this status update."""
        if self.review is None:
            return

        now = timezone.now()
        review_updated = False

        for comments in (self.review.comments,
                         self.review.screenshot_comments,
                         self.review.file_attachment_comments,
                         self.review.general_comments):
            open_comments = comments.filter(issue_status=BaseComment.OPEN)
            count = open_comments.update(issue_status=BaseComment.DROPPED,
                                         timestamp=now)

            if count > 0:
                review_updated = True

        if review_updated:
            self.review_request.last_review_activity_timestamp = now
            self.review_request.save(
                update_fields=['last_review_activity_timestamp'])
            self.review_request.reinit_issue_open_count()

    @property
    def can_run(self) -> bool:
        """Whether or not the checker associated can be run.

        Type:
            bool
        """
        state = self.effective_state
        return (state == StatusUpdate.NOT_YET_RUN or
                (state in {StatusUpdate.ERROR, StatusUpdate.TIMEOUT} and
                 self.extra_data.get('can_retry')))

    @property
    def action_name(self) -> StrOrPromise:
        """The name of the action to use for running or re-running the check.

        Type:
            str
        """
        if self.effective_state in {StatusUpdate.ERROR, StatusUpdate.TIMEOUT}:
            return gettext('Retry')
        else:
            return gettext('Run')

    def run(self) -> None:
        """Run the tool associated with this status update.

        This will emit the :py:data:`~reviewboard.reviews.signals.
        status_update_request_run` signal, which extensions/integrations
        providing manual run support should listen to. They're responsible
        for handling any filtering and configuration matching, as required.

        Version Changed:
            5.0.3:
            An associated integration config (if stored along with the status
            update) will be provided to the signal.
        """
        assert self.can_run
        status_update_request_run.send(sender=self.__class__,
                                       status_update=self,
                                       config=self.integration_config)

    class Meta:
        """Metadata for the model."""

        app_label = 'reviews'
        db_table = 'reviews_statusupdate'
        ordering = ['timestamp']
        get_latest_by = 'timestamp'
        verbose_name = _('Status Update')
        verbose_name_plural = _('Status Updates')
