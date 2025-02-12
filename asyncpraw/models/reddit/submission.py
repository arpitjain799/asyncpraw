"""Provide the Submission class."""
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from urllib.parse import urljoin
from warnings import warn

from asyncprawcore import Conflict

from ...const import API_PATH
from ...exceptions import InvalidURL
from ...util import _deprecate_args, cachedproperty
from ..comment_forest import CommentForest
from ..listing.listing import Listing
from ..listing.mixins import SubmissionListingMixin
from .base import RedditBase
from .mixins import FullnameMixin, ModNoteMixin, ThingModerationMixin, UserContentMixin
from .poll import PollData
from .redditor import Redditor
from .subreddit import Subreddit

if TYPE_CHECKING:  # pragma: no cover
    import asyncpraw


class SubmissionFlair:
    """Provide a set of functions pertaining to :class:`.Submission` flair."""

    def __init__(self, submission: "asyncpraw.models.Submission"):
        """Initialize a :class:`.SubmissionFlair` instance.

        :param submission: The :class:`.Submission` associated with the flair functions.

        """
        self.submission = submission

    async def choices(self) -> List[Dict[str, Union[bool, list, str]]]:
        """Return list of available flair choices.

        Choices are required in order to use :meth:`.select`.

        For example:

        .. code-block:: python

            choices = await submission.flair.choices()

        """
        if not self.submission._fetched:
            await self.submission._fetch()
        url = API_PATH["flairselector"].format(subreddit=self.submission.subreddit)
        data = await self.submission._reddit.post(
            url, data={"link": self.submission.fullname}
        )
        return data["choices"]

    @_deprecate_args("flair_template_id", "text")
    async def select(self, flair_template_id: str, *, text: Optional[str] = None):
        """Select flair for submission.

        :param flair_template_id: The flair template to select. The possible values can
            be discovered through :meth:`.choices`.
        :param text: If the template's ``flair_text_editable`` value is ``True``, this
            value will set a custom text (default: ``None``).

        For example, to select an arbitrary editable flair text (assuming there is one)
        and set a custom value try:

        .. code-block:: python

            choices = await submission.flair.choices()
            template_id = next(x for x in choices if x["flair_text_editable"])["flair_template_id"]
            await submission.flair.select(template_id, text="my custom value")

        """
        data = {
            "flair_template_id": flair_template_id,
            "link": self.submission.fullname,
            "text": text,
        }
        if not self.submission._fetched:
            await self.submission._fetch()
        url = API_PATH["select_flair"].format(subreddit=self.submission.subreddit)
        await self.submission._reddit.post(url, data=data)


class SubmissionModeration(ThingModerationMixin, ModNoteMixin):
    """Provide a set of functions pertaining to :class:`.Submission` moderation.

    Example usage:

    .. code-block:: python

        submission = await reddit.submission("8dmv8z", fetch=False)
        await submission.mod.approve()

    """

    REMOVAL_MESSAGE_API = "removal_link_message"

    def __init__(self, submission: "asyncpraw.models.Submission"):
        """Initialize a :class:`.SubmissionModeration` instance.

        :param submission: The submission to moderate.

        """
        self.thing = submission

    @_deprecate_args("state")
    async def contest_mode(self, *, state: bool = True):
        """Set contest mode for the comments of this submission.

        :param state: ``True`` enables contest mode and ``False`` disables (default:
            ``True``).

        Contest mode have the following effects:

        - The comment thread will default to being sorted randomly.
        - Replies to top-level comments will be hidden behind "[show replies]" buttons.
        - Scores will be hidden from non-moderators.
        - Scores accessed through the API (mobile apps, bots) will be obscured to "1"
          for non-moderators.

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("5or86n", fetch=False)
            await submission.mod.contest_mode()

        """
        await self.thing._reddit.post(
            API_PATH["contest_mode"], data={"id": self.thing.fullname, "state": state}
        )

    @_deprecate_args("text", "css_class", "flair_template_id")
    async def flair(
        self,
        *,
        css_class: str = "",
        flair_template_id: Optional[str] = None,
        text: str = "",
    ):
        """Set flair for the submission.

        :param css_class: The css class to associate with the flair html (default:
            ``""``).
        :param flair_template_id: The flair template ID to use when flairing.
        :param text: The flair text to associate with the :class:`.Submission` (default:
            ``""``).

        This method can only be used by an authenticated user who is a moderator of the
        submission's :class:`.Subreddit`.

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("5or86n", fetch=False)
            await submission.mod.flair(text="PRAW", css_class="bot")

        """
        data = {
            "css_class": css_class,
            "link": self.thing.fullname,
            "text": text,
        }
        if not self.thing._fetched:
            await self.thing._fetch()
        url = API_PATH["flair"].format(subreddit=self.thing.subreddit)
        if flair_template_id is not None:
            data["flair_template_id"] = flair_template_id
            url = API_PATH["select_flair"].format(subreddit=self.thing.subreddit)
        await self.thing._reddit.post(url, data=data)

    async def nsfw(self):
        """Mark as not safe for work.

        This method can be used both by the submission author and moderators of the
        subreddit that the submission belongs to.

        Example usage:

        .. code-block:: python

            subreddit = await reddit.subreddit("test")
            submission = await subreddit.submit("nsfw test", selftext="nsfw")
            await submission.mod.nsfw()

        .. seealso::

            :meth:`.sfw`

        """
        await self.thing._reddit.post(
            API_PATH["marknsfw"], data={"id": self.thing.fullname}
        )

    async def set_original_content(self):
        """Mark as original content.

        This method can be used by moderators of the subreddit that the submission
        belongs to. If the subreddit has enabled the Original Content beta feature in
        settings, then the submission's author can use it as well.

        Example usage:

        .. code-block:: python

            subreddit = await reddit.subreddit("test")
            submission = await subreddit.submit("oc test", selftext="original")
            await submission.mod.set_original_content()

        .. seealso::

            :meth:`.unset_original_content`

        """
        data = {
            "id": self.thing.id,
            "fullname": self.thing.fullname,
            "should_set_oc": True,
            "executed": False,
            "r": self.thing.subreddit,
        }
        await self.thing._reddit.post(API_PATH["set_original_content"], data=data)

    async def sfw(self):
        """Mark as safe for work.

        This method can be used both by the submission author and moderators of the
        subreddit that the submission belongs to.

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("5or86n", fetch=False)
            await submission.mod.sfw()

        .. seealso::

            :meth:`.nsfw`

        """
        await self.thing._reddit.post(
            API_PATH["unmarknsfw"], data={"id": self.thing.fullname}
        )

    async def spoiler(self):
        """Indicate that the submission contains spoilers.

        This method can be used both by the submission author and moderators of the
        subreddit that the submission belongs to.

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("5or86n", fetch=False)
            await submission.mod.spoiler()

        .. seealso::

            :meth:`.unspoiler`

        """
        await self.thing._reddit.post(
            API_PATH["spoiler"], data={"id": self.thing.fullname}
        )

    @_deprecate_args("state", "bottom")
    async def sticky(self, *, bottom: bool = True, state: bool = True):
        """Set the submission's sticky state in its subreddit.

        :param bottom: When ``True``, set the submission as the bottom sticky. If no top
            sticky exists, this submission will become the top sticky regardless
            (default: ``True``).
        :param state: ``True`` sets the sticky for the submission and ``False`` unsets
            (default: ``True``).

        .. note::

            When a submission is stickied two or more times, the Reddit API responds
            with a 409 error that is raised as a ``Conflict`` by asyncprawcore. This
            method suppresses these ``Conflict`` errors.

        This submission will replace the second stickied submission if one exists.

        For example:

        .. code-block:: python

            submission = await reddit.submission("5or86n", fetch=False)
            await submission.mod.sticky()

        """
        data = {"id": self.thing.fullname, "state": state}
        if not bottom:
            data["num"] = 1
        try:
            return await self.thing._reddit.post(
                API_PATH["sticky_submission"], data=data
            )
        except Conflict:
            pass

    @_deprecate_args("sort")
    async def suggested_sort(self, *, sort: str = "blank"):
        """Set the suggested sort for the comments of the submission.

        :param sort: Can be one of: ``"confidence"``, ``"top"``, ``"new"``,
            ``"controversial"``, ``"old"``, ``"random"``, ``"qa"``, or ``"blank"``
            (default: ``"blank"``).

        """
        await self.thing._reddit.post(
            API_PATH["suggested_sort"], data={"id": self.thing.fullname, "sort": sort}
        )

    async def unset_original_content(self):
        """Indicate that the submission is not original content.

        This method can be used by moderators of the subreddit that the submission
        belongs to. If the subreddit has enabled the Original Content beta feature in
        settings, then the submission's author can use it as well.

        Example usage:

        .. code-block:: python

            subreddit = await reddit.subreddit("test")
            submission = await subreddit.submit("oc test", selftext="original")
            await submission.mod.unset_original_content()

        .. seealso::

            :meth:`.set_original_content`

        """
        data = {
            "id": self.thing.id,
            "fullname": self.thing.fullname,
            "should_set_oc": False,
            "executed": False,
            "r": self.thing.subreddit,
        }
        await self.thing._reddit.post(API_PATH["set_original_content"], data=data)

    async def unspoiler(self):
        """Indicate that the submission does not contain spoilers.

        This method can be used both by the submission author and moderators of the
        subreddit that the submission belongs to.

        For example:

        .. code-block:: python

            sub = await reddit.subreddit("test")
            submission = await sub.submit("not spoiler", selftext="spoiler")
            await submission.mod.unspoiler()

        .. seealso::

            :meth:`.spoiler`

        """
        await self.thing._reddit.post(
            API_PATH["unspoiler"], data={"id": self.thing.fullname}
        )

    async def update_crowd_control_level(self, level: int):
        """Change the Crowd Control level of the submission.

        :param level: An integer between 0 and 3.

        **Level Descriptions**

        ===== ======== ================================================================
        Level Name     Description
        ===== ======== ================================================================
        0     Off      Crowd Control will not action any of the submission's comments.
        1     Lenient  Comments from users who have negative karma in the subreddit are
                       automatically collapsed.
        2     Moderate Comments from new users and users with negative karma in the
                       subreddit are automatically collapsed.
        3     Strict   Comments from users who haven’t joined the subreddit, new users,
                       and users with negative karma in the subreddit are automatically
                       collapsed.
        ===== ======== ================================================================

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("745ryj")
            await submission.mod.update_crowd_control_level(2)

        .. seealso::

            :meth:`~.CommentModeration.show`

        """
        await self.thing._reddit.post(
            API_PATH["update_crowd_control"],
            data={"id": self.thing.fullname, "level": level},
        )


class Submission(SubmissionListingMixin, UserContentMixin, FullnameMixin, RedditBase):
    """A class for submissions to Reddit.

    .. include:: ../../typical_attributes.rst

    ========================== =========================================================
    Attribute                  Description
    ========================== =========================================================
    ``author``                 Provides an instance of :class:`.Redditor`.
    ``author_flair_text``      The text content of the author's flair, or ``None`` if
                               not flaired.
    ``clicked``                Whether or not the submission has been clicked by the
                               client.
    ``comments``               Provides an instance of :class:`.CommentForest`.
    ``created_utc``            Time the submission was created, represented in `Unix
                               Time`_.
    ``distinguished``          Whether or not the submission is distinguished.
    ``edited``                 Whether or not the submission has been edited.
    ``id``                     ID of the submission.
    ``is_original_content``    Whether or not the submission has been set as original
                               content.
    ``is_self``                Whether or not the submission is a selfpost (text-only).
    ``link_flair_template_id`` The link flair's ID.
    ``link_flair_text``        The link flair's text content, or ``None`` if not
                               flaired.
    ``locked``                 Whether or not the submission has been locked.
    ``name``                   Fullname of the submission.
    ``num_comments``           The number of comments on the submission.
    ``over_18``                Whether or not the submission has been marked as NSFW.
    ``permalink``              A permalink for the submission.
    ``poll_data``              A :class:`.PollData` object representing the data of this
                               submission, if it is a poll submission.
    ``saved``                  Whether or not the submission is saved.
    ``score``                  The number of upvotes for the submission.
    ``selftext``               The submissions' selftext - an empty string if a link
                               post.
    ``spoiler``                Whether or not the submission has been marked as a
                               spoiler.
    ``stickied``               Whether or not the submission is stickied.
    ``subreddit``              Provides an instance of :class:`.Subreddit`.
    ``title``                  The title of the submission.
    ``upvote_ratio``           The percentage of upvotes from all votes on the
                               submission.
    ``url``                    The URL the submission links to, or the permalink if a
                               selfpost.
    ========================== =========================================================

    .. _unix time: https://en.wikipedia.org/wiki/Unix_time

    """

    STR_FIELD = "id"

    @staticmethod
    def id_from_url(url: str) -> str:
        """Return the ID contained within a submission URL.

        :param url: A url to a submission in one of the following formats (http urls
            will also work):

            - ``"https://redd.it/2gmzqe"``
            - ``"https://reddit.com/comments/2gmzqe/"``
            - ``"https://www.reddit.com/r/redditdev/comments/2gmzqe/praw_https/"``
            - ``"https://www.reddit.com/gallery/2gmzqe"``

        :raises: :class:`.InvalidURL` if ``url`` is not a valid submission URL.

        """
        parts = RedditBase._url_parts(url)
        if "comments" not in parts and "gallery" not in parts:
            submission_id = parts[-1]
            if "r" in parts:
                raise InvalidURL(
                    url, message="Invalid URL (subreddit, not submission): {}"
                )

        elif "gallery" in parts:
            submission_id = parts[parts.index("gallery") + 1]

        elif parts[-1] == "comments":
            raise InvalidURL(url, message="Invalid URL (submission ID not present): {}")

        else:
            submission_id = parts[parts.index("comments") + 1]

        if not submission_id.isalnum():
            raise InvalidURL(url)
        return submission_id

    @cachedproperty
    def flair(self) -> SubmissionFlair:
        """Provide an instance of :class:`.SubmissionFlair`.

        This attribute is used to work with flair as a regular user of the subreddit the
        submission belongs to. Moderators can directly use :meth:`.flair`.

        For example, to select an arbitrary editable flair text (assuming there is one)
        and set a custom value try:

        .. code-block:: python

            choices = await submission.flair.choices()
            template_id = next(x for x in choices if x["flair_text_editable"])["flair_template_id"]
            await submission.flair.select(template_id, text="my custom value")

        """
        return SubmissionFlair(self)

    @cachedproperty
    def mod(self) -> SubmissionModeration:
        """Provide an instance of :class:`.SubmissionModeration`.

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("8dmv8z", fetch=False)
            await submission.mod.approve()

        """
        return SubmissionModeration(self)

    @property
    def _kind(self) -> str:
        """Return the class's kind."""
        return self._reddit.config.kinds["submission"]

    @property
    def shortlink(self) -> str:
        """Return a shortlink to the submission.

        For example, https://redd.it/eorhm is a shortlink for
        https://www.reddit.com/r/announcements/comments/eorhm/reddit_30_less_typing/.

        """
        return urljoin(self._reddit.config.short_url, self.id)

    def __init__(
        self,
        reddit: "asyncpraw.Reddit",
        id: Optional[str] = None,  # pylint: disable=redefined-builtin
        url: Optional[str] = None,
        _data: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a :class:`.Submission` instance.

        :param reddit: An instance of :class:`.Reddit`.
        :param id: A reddit base36 submission ID, e.g., ``"2gmzqe"``.
        :param url: A URL supported by :meth:`.id_from_url`.

        Either ``id`` or ``url`` can be provided, but not both.

        """
        if (id, url, _data).count(None) != 2:
            raise TypeError("Exactly one of 'id', 'url', or '_data' must be provided.")
        self.comment_limit = 2048

        # Specify the sort order for ``comments``
        self.comment_sort = "confidence"

        if id:
            self.id = id
        elif url:
            self.id = self.id_from_url(url)

        super().__init__(reddit, _data=_data)

        self._comments_by_id = {}
        self.comments = CommentForest(self)
        """Provide an instance of :class:`.CommentForest`.

        This attribute can be used, for example, to obtain a flat list of comments, with
        any :class:`.MoreComments` removed:

        .. code-block:: python

            await submission.comments.replace_more(limit=0)
            comments = submission.comments.list()

        :raises: :py:class:`TypeError` if the submission is not fetched.

        Sort order and comment limit must be set with the ``comment_sort`` and
        ``comment_limit`` attributes before the submission and its comments are fetched,
        including any call to :meth:`.replace_more`. The ``fetch`` argument will need to
        set when initializing the :class:`.Submission` instance:

        .. code-block:: python

            submission = await reddit.submission("8dmv8z", fetch=False)
            submission.comment_sort = "new"
            await submission.load()
            comments = submission.comments.list()

        .. note::

            The appropriate values for ``comment_sort`` include ``confidence``,
            ``controversial``, ``new``, ``old``, ``q&a``, and ``top``

        See :ref:`extracting_comments` for more on working with a
        :class:`.CommentForest`.

        """

    def __setattr__(self, attribute: str, value: Any):
        """Objectify author, subreddit, and poll data attributes."""
        if attribute == "author":
            value = Redditor.from_data(self._reddit, value)
        elif attribute == "subreddit":
            value = Subreddit(self._reddit, value)
        elif attribute == "poll_data":
            value = PollData(self._reddit, value)
        elif (
            attribute == "comment_sort"
            and hasattr(self, "_fetched")
            and self._fetched
            and hasattr(self, "_reddit")
            and self._reddit.config.warn_comment_sort
        ):
            warn(
                "The comments for this submission have already been fetched, "
                "so the updated comment_sort will not have any effect"
            )
        super().__setattr__(attribute, value)

    def _chunk(self, *, chunk_size, other_submissions):
        all_submissions = [self.fullname]
        if other_submissions:
            all_submissions += [x.fullname for x in other_submissions]

        for position in range(0, len(all_submissions), chunk_size):
            yield ",".join(all_submissions[position : position + 50])

    async def _fetch(self):
        data = await self._fetch_data()
        submission_listing, comment_listing = data
        comment_listing = Listing(self._reddit, _data=comment_listing["data"])

        submission_data = submission_listing["data"]["children"][0]["data"]
        submission = type(self)(self._reddit, _data=submission_data)
        delattr(submission, "comment_limit")
        delattr(submission, "comment_sort")
        submission.comments = CommentForest(self)

        self.__dict__.update(submission.__dict__)
        self._fetched = True
        self.comments._update(comment_listing.children)

    async def _fetch_data(self):
        name, fields, params = self._fetch_info()
        path = API_PATH[name].format(**fields)
        return await self._reddit.request(method="GET", params=params, path=path)

    def _fetch_info(self):
        return (
            "submission",
            {"id": self.id},
            {"limit": self.comment_limit, "sort": self.comment_sort},
        )

    @_deprecate_args(
        "subreddit",
        "title",
        "send_replies",
        "flair_id",
        "flair_text",
        "nsfw",
        "spoiler",
    )
    async def crosspost(
        self,
        subreddit: "asyncpraw.models.Subreddit",
        *,
        flair_id: Optional[str] = None,
        flair_text: Optional[str] = None,
        nsfw: bool = False,
        send_replies: bool = True,
        spoiler: bool = False,
        title: Optional[str] = None,
    ) -> "asyncpraw.models.Submission":
        """Crosspost the submission to a subreddit.

        .. note::

            Be aware you have to be subscribed to the target subreddit.

        :param subreddit: Name of the subreddit or :class:`.Subreddit` object to
            crosspost into.
        :param flair_id: The flair template to select (default: ``None``).
        :param flair_text: If the template's ``flair_text_editable`` value is ``True``,
            this value will set a custom text (default: ``None``).
        :param nsfw: Whether the submission should be marked NSFW (default: ``False``).
        :param send_replies: When ``True``, messages will be sent to the created
            submission's author when comments are made to the submission (default:
            ``True``).
        :param spoiler: Whether the submission should be marked as a spoiler (default:
            ``False``).
        :param title: Title of the submission. Will use this submission's title if
            ``None`` (default: ``None``).

        :returns: A :class:`.Submission` object for the newly created submission.

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("5or86n")
            cross_post = await submission.crosspost("learnprogramming", send_replies=False)

        .. seealso::

            :meth:`.hide`

        """
        if title is None:
            title = self.title

        data = {
            "sr": str(subreddit),
            "title": title,
            "sendreplies": bool(send_replies),
            "kind": "crosspost",
            "crosspost_fullname": self.fullname,
            "nsfw": bool(nsfw),
            "spoiler": bool(spoiler),
        }
        for key, value in (("flair_id", flair_id), ("flair_text", flair_text)):
            if value is not None:
                data[key] = value

        return await self._reddit.post(API_PATH["submit"], data=data)

    @_deprecate_args("other_submissions")
    async def hide(
        self, *, other_submissions: Optional[List["asyncpraw.models.Submission"]] = None
    ):
        """Hide :class:`.Submission`.

        :param other_submissions: When provided, additionally hide this list of
            :class:`.Submission` instances as part of a single request (default:
            ``None``).

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("5or86n", fetch=False)
            await submission.hide()

        .. seealso::

            :meth:`.unhide`

        """
        for submissions in self._chunk(
            chunk_size=50, other_submissions=other_submissions
        ):
            await self._reddit.post(API_PATH["hide"], data={"id": submissions})

    async def mark_visited(self):
        """Mark submission as visited.

        This method requires a subscription to reddit premium.

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("5or86n", fetch=False)
            await submission.mark_visited()

        """
        data = {"links": self.fullname}
        await self._reddit.post(API_PATH["store_visits"], data=data)

    @_deprecate_args("other_submissions")
    async def unhide(
        self, *, other_submissions: Optional[List["asyncpraw.models.Submission"]] = None
    ):
        """Unhide :class:`.Submission`.

        :param other_submissions: When provided, additionally unhide this list of
            :class:`.Submission` instances as part of a single request (default:
            ``None``).

        Example usage:

        .. code-block:: python

            submission = await reddit.submission("5or86n", fetch=False)
            await submission.unhide()

        .. seealso::

            :meth:`.hide`

        """
        for submissions in self._chunk(
            chunk_size=50, other_submissions=other_submissions
        ):
            await self._reddit.post(API_PATH["unhide"], data={"id": submissions})


Subreddit._submission_class = Submission
