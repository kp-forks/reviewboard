"""Unit tests for RootDiffCommentResource."""

from datetime import timedelta
from django.utils import timezone
from djblets.testing.decorators import add_fixtures
from djblets.webapi.testing.decorators import webapi_test_template

from reviewboard.webapi.resources import resources
from reviewboard.webapi.tests.base import BaseWebAPITestCase
from reviewboard.webapi.tests.mimetypes import \
    review_diff_comment_list_mimetype
from reviewboard.webapi.tests.mixins import BasicTestsMetaclass
from reviewboard.webapi.tests.urls import get_root_diff_comment_list_url


class ResourceListTests(BaseWebAPITestCase,
                        metaclass=BasicTestsMetaclass):
    """Testing the RootDiffCommentResource API."""

    fixtures = ['test_scmtools', 'test_users']
    sample_api_url = 'diff-comments/'
    resource = resources.root_diff_comment
    test_http_methods = ('GET',)

    def compare_item(self, item_rsp, comment):
        """Compare a comment item to a comment returned from the API.

        Args:
            item_rsp (dict):
                The serialized comment returned from the API.

            comment (reviewboard.reviews.models.Comment):
                The comment instance to compare to.

        Raises:
            AssertionError:
                The API response was not equivalent to the object.
        """
        self.assertEqual(item_rsp['id'], comment.pk)
        self.assertEqual(item_rsp['text'], comment.text)
        self.assertEqual(item_rsp['issue_opened'], comment.issue_opened)
        self.assertEqual(item_rsp['first_line'], comment.first_line)
        self.assertEqual(item_rsp['num_lines'], comment.num_lines)

        self.assertEqual(item_rsp['extra_data'],
                         self.resource._strip_private_data(comment.extra_data))

        if comment.rich_text:
            self.assertEqual(item_rsp['text_type'], 'markdown')
        else:
            self.assertEqual(item_rsp['text_type'], 'plain')

    #
    # HTTP GET tests
    #

    def setup_basic_get_test(self, user, with_local_site, local_site_name,
                             populate_items):
        review_request = self.create_review_request(
            create_repository=True,
            with_local_site=with_local_site,
            submitter=user,
            publish=True)
        diffset = self.create_diffset(review_request)
        filediff = self.create_filediff(diffset)
        review = self.create_review(review_request, publish=True)

        if populate_items:
            items = [self.create_diff_comment(review, filediff)]
        else:
            items = []

        return (get_root_diff_comment_list_url(local_site_name),
                review_diff_comment_list_mimetype,
                items)

    @webapi_test_template
    def test_comment_is_same_as_canonical_comment(self):
        """Testing the GET <URL>/ API returns a proper data type"""
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review = self.create_review(review_request, publish=True)
        comment = self._create_diff_comment(review_request, review)

        rsp = self.api_get(get_root_diff_comment_list_url(), {},
                           expected_mimetype=review_diff_comment_list_mimetype)

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp[self.resource.list_result_key][0], comment)

    @webapi_test_template
    def test_get_with_counts_only(self):
        """"Testing the GET <URL>/?counts-only=1 API"""
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review = self.create_review(review_request, publish=True)
        self._create_diff_comment(review_request, review)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'counts-only': 1,
        }, expected_mimetype=review_diff_comment_list_mimetype)

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'], review.comments.count())

    @webapi_test_template
    def test_get(self):
        """"Testing the GET <URL>/? API returns only comments from reviews
        and review requests that the requester has access to
        """
        repo = self.create_repository(public=False)
        review_request_inaccessible = \
            self.create_review_request(repository=repo)
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review1 = self.create_review(review_request, publish=True)
        review2 = self.create_review(review_request, publish=False)
        review3 = self.create_review(review_request, user=self.user,
                                     publish=True)
        review4 = self.create_review(review_request, user=self.user,
                                     publish=False)
        review5 = self.create_review(review_request_inaccessible,
                                     publish=True)
        review6 = self.create_review(review_request_inaccessible,
                                     publish=False)

        comment1 = self._create_diff_comment(review_request, review1)
        self._create_diff_comment(review_request, review2)
        comment3 = self._create_diff_comment(review_request, review3)
        comment4 = self._create_diff_comment(review_request, review4)
        self._create_diff_comment(review_request_inaccessible, review5)
        self._create_diff_comment(review_request_inaccessible, review6)

        rsp = self.api_get(get_root_diff_comment_list_url(), {},
                           expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 3)
        self.compare_item(rsp_items[0], comment1)
        self.compare_item(rsp_items[1], comment3)
        self.compare_item(rsp_items[2], comment4)

    @webapi_test_template
    def test_get_by_repo(self):
        """Testing the GET <URL>/ API returns only comments from
        repositories that the requester has access to
        """
        group1 = self.create_review_group()
        group2 = self.create_review_group()
        group1.users.add(self.user)
        user = self.create_user()

        repo1 = self.create_repository(name='repo1', public=True)
        repo2 = self.create_repository(name='repo2', public=False)
        repo3 = self.create_repository(name='repo3', public=False)
        repo4 = self.create_repository(name='repo4', public=False)
        repo5 = self.create_repository(name='repo2', public=False)
        repo6 = self.create_repository(name='repo3', public=False)
        repo2.users.add(self.user)
        repo3.review_groups.add(group1)
        repo5.users.add(user)
        repo6.review_groups.add(group2)

        review_request1 = self.create_review_request(publish=True,
                                                     repository=repo1)
        review_request2 = self.create_review_request(publish=True,
                                                     repository=repo2)
        review_request3 = self.create_review_request(publish=True,
                                                     repository=repo3)
        review_request4 = self.create_review_request(publish=True,
                                                     repository=repo4)
        review_request5 = self.create_review_request(publish=True,
                                                     repository=repo5)
        review_request6 = self.create_review_request(publish=True,
                                                     repository=repo6)

        review1 = self.create_review(review_request1, publish=True)
        review2 = self.create_review(review_request2, publish=True)
        review3 = self.create_review(review_request3, publish=True)
        review4 = self.create_review(review_request4, publish=True)
        review5 = self.create_review(review_request5, publish=True)
        review6 = self.create_review(review_request6, publish=True)

        comment1 = self._create_diff_comment(review_request1, review1)
        comment2 = self._create_diff_comment(review_request2, review2)
        comment3 = self._create_diff_comment(review_request3, review3)
        self._create_diff_comment(review_request4, review4)
        self._create_diff_comment(review_request5, review5)
        self._create_diff_comment(review_request6, review6)

        rsp = self.api_get(get_root_diff_comment_list_url(), {},
                           expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 3)
        self.compare_item(rsp_items[0], comment1)
        self.compare_item(rsp_items[1], comment2)
        self.compare_item(rsp_items[2], comment3)

    @webapi_test_template
    def test_get_by_review_group(self):
        """Testing the GET <URL>/ API returns only comments associated
        with review groups that the requester has access to
        """
        group1 = self.create_review_group(name='group1', invite_only=False)
        group2 = self.create_review_group(name='group2', invite_only=True)
        group3 = self.create_review_group(name='group3', invite_only=False)
        group4 = self.create_review_group(name='group4', invite_only=True)
        group1.users.add(self.user)
        group2.users.add(self.user)
        repo = self.create_repository(public=False)
        repo.review_groups.add(group4)

        review_request1 = self.create_review_request(publish=True,
                                                     create_repository=True)
        review_request2 = self.create_review_request(publish=True,
                                                     create_repository=True)
        review_request3 = self.create_review_request(publish=True,
                                                     create_repository=True)
        review_request4 = self.create_review_request(publish=True,
                                                     create_repository=True)
        review_request5 = self.create_review_request(publish=True,
                                                     repository=repo)
        review_request1.target_groups.add(group1)
        review_request2.target_groups.add(group2)
        review_request3.target_groups.add(group3)
        review_request4.target_groups.add(group4)

        review1 = self.create_review(review_request1, publish=True)
        review2 = self.create_review(review_request2, publish=True)
        review3 = self.create_review(review_request3, publish=True)
        review4 = self.create_review(review_request4, publish=True)
        review5 = self.create_review(review_request5, publish=True)

        comment1 = self._create_diff_comment(review_request1, review1)
        comment2 = self._create_diff_comment(review_request2, review2)
        comment3 = self._create_diff_comment(review_request3, review3)
        self._create_diff_comment(review_request4, review4)
        self._create_diff_comment(review_request5, review5)

        rsp = self.api_get(get_root_diff_comment_list_url(), {},
                           expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 3)
        self.compare_item(rsp_items[0], comment1)
        self.compare_item(rsp_items[1], comment2)
        self.compare_item(rsp_items[2], comment3)

    @add_fixtures(['test_site'])
    @webapi_test_template
    def test_get_by_local_site(self):
        """Testing the GET <URL> API returns only comments from local
        sites that the requester has access to
        """
        local_site1 = self.get_local_site(self.local_site_name)
        local_site2 = self.get_local_site('local-site-2')
        local_site2.users.add(self.user)
        review_request1 = self.create_review_request(publish=True,
                                                     local_site=local_site1,
                                                     create_repository=True)
        review_request2 = self.create_review_request(publish=True,
                                                     local_site=local_site2,
                                                     create_repository=True)
        review_request3 = self.create_review_request(publish=True,
                                                     create_repository=True)

        review1 = self.create_review(review_request1, publish=True, user='doc')
        review2 = self.create_review(review_request2, user=self.user,
                                     publish=True)
        review3 = self.create_review(review_request3, publish=True)

        self._create_diff_comment(review_request1, review1)
        comment2 = self._create_diff_comment(review_request2, review2)
        comment3 = self._create_diff_comment(review_request3, review3)

        rsp = self.api_get(
            get_root_diff_comment_list_url(local_site_name=local_site1.name),
            {'counts-only': 1},
            expected_status=403)
        self.assertEqual(rsp['stat'], 'fail')

        rsp = self.api_get(
            get_root_diff_comment_list_url(local_site_name=local_site2.name),
            {},
            expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment2)

        rsp = self.api_get(get_root_diff_comment_list_url(), {},
                           expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment3)

    @webapi_test_template
    def test_get_with_review_id(self):
        """"Testing the GET <URL>/?review-id=<id> API returns only comments from
        reviews that the requester has access to
        """
        repo = self.create_repository(public=False)
        review_request_inaccessible = \
            self.create_review_request(repository=repo)
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review1 = self.create_review(review_request, publish=True)
        review2 = self.create_review(review_request, publish=False)
        review3 = self.create_review(review_request, user=self.user,
                                     publish=True)
        review4 = self.create_review(review_request, user=self.user,
                                     publish=False)
        review5 = self.create_review(review_request_inaccessible,
                                     publish=True)
        review6 = self.create_review(review_request_inaccessible,
                                     publish=False)

        comment1 = self._create_diff_comment(review_request, review1)
        self._create_diff_comment(review_request, review2)
        self._create_diff_comment(review_request, review3)
        comment4 = self._create_diff_comment(review_request, review4)
        self._create_diff_comment(review_request_inaccessible, review5)
        self._create_diff_comment(review_request_inaccessible, review6)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'review-id': review1.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment1)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'review-id': review2.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 0)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'review-id': review4.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment4)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'review-id': review5.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 0)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'review-id': -1,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 0)

    @webapi_test_template
    def test_get_with_review_request(self):
        """"Testing the GET <URL>/?review-request-id=<id> API returns
        only comments from review requests that the requester has access to
        """
        repo = self.create_repository(public=False)
        review_request_inaccessible = \
            self.create_review_request(repository=repo)
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review1 = self.create_review(review_request, publish=True)
        review2 = self.create_review(review_request, publish=False)
        review3 = self.create_review(review_request, user=self.user,
                                     publish=True)
        review4 = self.create_review(review_request, user=self.user,
                                     publish=False)
        review5 = self.create_review(review_request_inaccessible,
                                     publish=True)
        review6 = self.create_review(review_request_inaccessible,
                                     publish=False)

        comment1 = self._create_diff_comment(review_request, review1)
        self._create_diff_comment(review_request, review2)
        comment3 = self._create_diff_comment(review_request, review3)
        comment4 = self._create_diff_comment(review_request, review4)
        self._create_diff_comment(review_request_inaccessible, review5)
        self._create_diff_comment(review_request_inaccessible, review6)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'review-request-id': review_request.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 3)
        self.compare_item(rsp_items[0], comment1)
        self.compare_item(rsp_items[1], comment3)
        self.compare_item(rsp_items[2], comment4)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'review-request-id': review_request_inaccessible.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 0)

    @add_fixtures(['test_site'])
    @webapi_test_template
    def test_get_with_review_request_from_local_site(self):
        """"Testing the GET <URL>/?review-request-id=<id> API with a LocalSite
        bound review request ID
        """
        review_request1 = self.create_review_request(publish=True,
                                                     create_repository=True)
        review1 = self.create_review(review_request1, publish=True)
        comment1 = self._create_diff_comment(review_request1, review1)

        local_site1 = self.get_local_site(self.local_site_name)
        local_site1.users.add(self.user)
        review_request2 = self.create_review_request(publish=True,
                                                     local_site=local_site1,
                                                     create_repository=True)
        review2 = self.create_review(review_request2, user=self.user,
                                     publish=True)
        comment2 = self._create_diff_comment(review_request2, review2,
                                             text='localsite')

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'review-request-id': review_request1.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment1)

        rsp = self.api_get(
            get_root_diff_comment_list_url(local_site_name=local_site1.name),
            {'review-request-id': review_request2.local_id},
            expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment2)

    @webapi_test_template
    def test_get_with_user(self):
        """"Testing the GET <URL>/?user=<user-name> API returns comments
        by user
        """
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        user1 = self.create_user(username='user1')
        user2 = self.create_user(username='user2')
        review1 = self.create_review(review_request, publish=True, user=user1)
        review2 = self.create_review(review_request, publish=True, user=user2)
        review3 = self.create_review(review_request, publish=False, user=user2)

        comment1 = self._create_diff_comment(review_request, review1)
        comment2 = self._create_diff_comment(review_request, review2)
        self._create_diff_comment(review_request, review3)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'user': 'user1',
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment1)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'user': 'user2',
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment2)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'user': 'user3',
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 0)

    @webapi_test_template
    def test_get_with_file_diff_id(self):
        """"Testing the GET <URL>/?file-diff-id=<id> API"""
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review = self.create_review(review_request, publish=True)
        diffset = self.create_diffset(review_request)
        filediff1 = self.create_filediff(diffset)
        filediff2 = self.create_filediff(diffset)
        comment1 = self.create_diff_comment(review, filediff1)
        comment2 = self.create_diff_comment(review, filediff2)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'file-diff-id': filediff1.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment1)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'file-diff-id': filediff2.id,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment2)

    @webapi_test_template
    def test_get_by_last_updated_from_includes_from_date(self):
        """Testing the GET <URL>/?last-updated-from=<date> API
        returns only comments within the from date
        """
        now = timezone.now()
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review = self.create_review(review_request, publish=True,
                                    timestamp=(now - timedelta(hours=1)))
        diffset = self.create_diffset(review_request)
        filediff = self.create_filediff(diffset=diffset)

        self.create_diff_comment(review, filediff,
                                 timestamp=(now - timedelta(hours=1)))
        comment2 = self.create_diff_comment(
            review,
            filediff,
            timestamp=(now + timedelta(hours=1)))

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'last-updated-from': now.isoformat(),
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment2)

    @webapi_test_template
    def test_get_by_last_updated_to_includes_to_date(self):
        """Testing the GET <URL>/?last-updated-to=<date>
        API returns only comments within the to date
        """
        now = timezone.now()
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review1 = self.create_review(review_request, publish=True,
                                     timestamp=(now - timedelta(hours=1)))
        diffset = self.create_diffset(review_request)
        filediff = self.create_filediff(diffset=diffset)
        comment1 = self.create_diff_comment(
            review1,
            filediff,
            timestamp=(now - timedelta(hours=1)))
        self.create_diff_comment(review1, filediff,
                                 timestamp=(now + timedelta(hours=1)))

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'last-updated-to': now.isoformat(),
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment1)

    @webapi_test_template
    def test_get_by_last_updated_to_and_from_simple_date_format(self):
        """Testing the GET
        <URL>/?last-updated-from=<date>&last-updated-to=<date>
        API returns only comments within the from and to date
        """
        timestamp_from = timezone.now()
        timestamp_to = timezone.now() + timedelta(hours=1)
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review1 = self.create_review(
            review_request,
            publish=True,
            timestamp=(timestamp_from - timedelta(minutes=30)))
        diffset = self.create_diffset(review_request)
        filediff = self.create_filediff(diffset=diffset)
        self.create_diff_comment(
            review1,
            filediff,
            timestamp=(timestamp_from - timedelta(minutes=30)))
        comment2 = self.create_diff_comment(
            review1,
            filediff,
            timestamp=(timestamp_from + timedelta(minutes=30)))
        self.create_diff_comment(
            review1,
            filediff,
            timestamp=(timestamp_to + timedelta(minutes=30)))

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'last-updated-from': timestamp_from.isoformat(),
            'last-updated-to': timestamp_to.isoformat(),
        }, expected_mimetype=review_diff_comment_list_mimetype)
        rsp_items = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(rsp_items[0], comment2)

    @webapi_test_template
    def test_get_with_is_reply(self):
        """Testing the GET <URL>/?is-reply=1 API"""
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        review = self.create_review(review_request, publish=True)
        comment1 = self._create_diff_comment(review_request, review)
        comment2 = self._create_diff_comment(review_request, review,
                                             reply_to=comment1)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'is-reply': 1,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        items_rsp = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(items_rsp[0], comment2)

    @webapi_test_template
    def test_get_with_interdiff(self):
        """Testing the GET <URL>/?interdiff-revision= API"""
        review_request = self.create_review_request(publish=True,
                                                    create_repository=True)
        diffset = self.create_diffset(review_request)
        filediff = self.create_filediff(diffset)
        interdiffset = self.create_diffset(review_request)
        interfilediff = self.create_filediff(diffset)
        review = self.create_review(review_request, user=self.user)
        comment = self.create_diff_comment(review, filediff, interfilediff)

        rsp = self.api_get(get_root_diff_comment_list_url(), {
            'interdiff-revision': interdiffset.revision,
        }, expected_mimetype=review_diff_comment_list_mimetype)
        items_rsp = rsp[self.resource.list_result_key]

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['total_results'], 1)
        self.compare_item(items_rsp[0], comment)

    def _create_diff_comment(self, review_request, review, **kwargs):
        """Creates a diff comment.

        Args:
            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request that the comment will be on.

            review (reviewboard.reviews.models.Review):
                The review that the comment will be on.

            **kwargs (dict):
                Additional keyword arguments to pass to
                :py:meth:`create_diff_comment`.

        Returns:
            reviewboard.reviews.models.Comment:
            The comment.
        """
        diffset = self.create_diffset(review_request)
        filediff = self.create_filediff(diffset=diffset)

        return self.create_diff_comment(review, filediff, **kwargs)
