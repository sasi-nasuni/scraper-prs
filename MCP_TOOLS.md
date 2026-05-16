# MCP Server Tools Reference

*Auto-generated on 2026-04-21 00:06*

This document lists all tools available from the configured MCP servers.

---

## GitHub MCP Server

**Total tools: 26**

### Branches / Commits / Tags (2)

#### `create_branch`
> Create a new branch in a GitHub repository

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `branch` (string) **(required)** — Name for the new branch
  - `from_branch` (string) *(optional)* — Optional: source branch to create from (defaults to the repository's default branch)

#### `list_commits`
> Get list of commits of a branch in a GitHub repository

**Parameters:**
  - `owner` (string) **(required)**
  - `repo` (string) **(required)**
  - `sha` (string) *(optional)*
  - `page` (number) *(optional)*
  - `perPage` (number) *(optional)*

### Files & Content (3)

#### `create_or_update_file`
> Create or update a single file in a GitHub repository

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `path` (string) **(required)** — Path where to create/update the file
  - `content` (string) **(required)** — Content of the file
  - `message` (string) **(required)** — Commit message
  - `branch` (string) **(required)** — Branch to create/update the file in
  - `sha` (string) *(optional)* — SHA of the file being replaced (required when updating existing files)

#### `get_file_contents`
> Get the contents of a file or directory from a GitHub repository

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `path` (string) **(required)** — Path to the file or directory
  - `branch` (string) *(optional)* — Branch to get contents from

#### `push_files`
> Push multiple files to a GitHub repository in a single commit

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `branch` (string) **(required)** — Branch to push to (e.g., 'main' or 'master')
  - `files` (array) **(required)** — Array of files to push
  - `message` (string) **(required)** — Commit message

### Issues (6)

#### `add_issue_comment`
> Add a comment to an existing issue

**Parameters:**
  - `owner` (string) **(required)**
  - `repo` (string) **(required)**
  - `issue_number` (number) **(required)**
  - `body` (string) **(required)**

#### `create_issue`
> Create a new issue in a GitHub repository

**Parameters:**
  - `owner` (string) **(required)**
  - `repo` (string) **(required)**
  - `title` (string) **(required)**
  - `body` (string) *(optional)*
  - `assignees` (array) *(optional)*
  - `milestone` (number) *(optional)*
  - `labels` (array) *(optional)*

#### `get_issue`
> Get details of a specific issue in a GitHub repository.

**Parameters:**
  - `owner` (string) **(required)**
  - `repo` (string) **(required)**
  - `issue_number` (number) **(required)**

#### `list_issues`
> List issues in a GitHub repository with filtering options

**Parameters:**
  - `owner` (string) **(required)**
  - `repo` (string) **(required)**
  - `direction` (string) *(optional)*
  - `labels` (array) *(optional)*
  - `page` (number) *(optional)*
  - `per_page` (number) *(optional)*
  - `since` (string) *(optional)*
  - `sort` (string) *(optional)*
  - `state` (string) *(optional)*

#### `search_issues`
> Search for issues and pull requests across GitHub repositories

**Parameters:**
  - `q` (string) **(required)**
  - `order` (string) *(optional)*
  - `page` (number) *(optional)*
  - `per_page` (number) *(optional)*
  - `sort` (string) *(optional)*

#### `update_issue`
> Update an existing issue in a GitHub repository

**Parameters:**
  - `owner` (string) **(required)**
  - `repo` (string) **(required)**
  - `issue_number` (number) **(required)**
  - `title` (string) *(optional)*
  - `body` (string) *(optional)*
  - `assignees` (array) *(optional)*
  - `milestone` (number) *(optional)*
  - `labels` (array) *(optional)*
  - `state` (string) *(optional)*

### Pull Requests (10)

#### `create_pull_request`
> Create a new pull request in a GitHub repository

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `title` (string) **(required)** — Pull request title
  - `body` (string) *(optional)* — Pull request body/description
  - `head` (string) **(required)** — The name of the branch where your changes are implemented
  - `base` (string) **(required)** — The name of the branch you want the changes pulled into
  - `draft` (boolean) *(optional)* — Whether to create the pull request as a draft
  - `maintainer_can_modify` (boolean) *(optional)* — Whether maintainers can modify the pull request

#### `create_pull_request_review`
> Create a review on a pull request

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `pull_number` (number) **(required)** — Pull request number
  - `commit_id` (string) *(optional)* — The SHA of the commit that needs a review
  - `body` (string) **(required)** — The body text of the review
  - `event` (string) **(required)** — The review action to perform
  - `comments` (array) *(optional)* — Comments to post as part of the review (specify either position or line, not both)

#### `get_pull_request`
> Get details of a specific pull request

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `pull_number` (number) **(required)** — Pull request number

#### `get_pull_request_comments`
> Get the review comments on a pull request

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `pull_number` (number) **(required)** — Pull request number

#### `get_pull_request_files`
> Get the list of files changed in a pull request

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `pull_number` (number) **(required)** — Pull request number

#### `get_pull_request_reviews`
> Get the reviews on a pull request

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `pull_number` (number) **(required)** — Pull request number

#### `get_pull_request_status`
> Get the combined status of all status checks for a pull request

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `pull_number` (number) **(required)** — Pull request number

#### `list_pull_requests`
> List and filter repository pull requests

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `state` (string) *(optional)* — State of the pull requests to return
  - `head` (string) *(optional)* — Filter by head user or head organization and branch name
  - `base` (string) *(optional)* — Filter by base branch name
  - `sort` (string) *(optional)* — What to sort results by
  - `direction` (string) *(optional)* — The direction of the sort
  - `per_page` (number) *(optional)* — Results per page (max 100)
  - `page` (number) *(optional)* — Page number of the results

#### `merge_pull_request`
> Merge a pull request

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `pull_number` (number) **(required)** — Pull request number
  - `commit_title` (string) *(optional)* — Title for the automatic commit message
  - `commit_message` (string) *(optional)* — Extra detail to append to automatic commit message
  - `merge_method` (string) *(optional)* — Merge method to use

#### `update_pull_request_branch`
> Update a pull request branch with the latest changes from the base branch

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `pull_number` (number) **(required)** — Pull request number
  - `expected_head_sha` (string) *(optional)* — The expected SHA of the pull request's HEAD ref

### Repositories (3)

#### `create_repository`
> Create a new GitHub repository in your account

**Parameters:**
  - `name` (string) **(required)** — Repository name
  - `description` (string) *(optional)* — Repository description
  - `private` (boolean) *(optional)* — Whether the repository should be private
  - `autoInit` (boolean) *(optional)* — Initialize with README.md

#### `fork_repository`
> Fork a GitHub repository to your account or specified organization

**Parameters:**
  - `owner` (string) **(required)** — Repository owner (username or organization)
  - `repo` (string) **(required)** — Repository name
  - `organization` (string) *(optional)* — Optional: organization to fork to (defaults to your personal account)

#### `search_repositories`
> Search for GitHub repositories

**Parameters:**
  - `query` (string) **(required)** — Search query (see GitHub search syntax)
  - `page` (number) *(optional)* — Page number for pagination (default: 1)
  - `perPage` (number) *(optional)* — Number of results per page (default: 30, max: 100)

### Search (1)

#### `search_code`
> Search for code across GitHub repositories

**Parameters:**
  - `q` (string) **(required)**
  - `order` (string) *(optional)*
  - `page` (number) *(optional)*
  - `per_page` (number) *(optional)*

### Users (1)

#### `search_users`
> Search for users on GitHub

**Parameters:**
  - `q` (string) **(required)**
  - `order` (string) *(optional)*
  - `page` (number) *(optional)*
  - `per_page` (number) *(optional)*
  - `sort` (string) *(optional)*

---

## Atlassian MCP Server

**Total tools: 31**

### Confluence (7)

#### `createConfluencePage`
> Create a Confluence page or blog post

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `spaceId` (string) **(required)** — Space ID
  - `contentType` (string) *(optional)* — Type of content: page or blog post
  - `title` (string) *(optional)* — Page or blog post title
  - `status` (string) *(optional)* — Status (draft for unpublished)
  - `parentId` (string) *(optional)* — Parent page ID (pages only, ignored for blogs)
  - `body` (string) **(required)** — Page content
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.
  - `isPrivate` (boolean) *(optional)* — Make private
  - `subtype` (string) *(optional)* — Page subtype (pages only, ignored for blogs)

#### `getConfluencePage`
> Get a Confluence page or blog post by ID, including body content.

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `pageId` (string) **(required)** — Page or blog post ID, or a Confluence tiny link ID (the encoded part from /wiki/x/ URLs, e.g., Fc1bBw)
  - `contentType` (string) *(optional)* — Type of content: page or blog post
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `getConfluencePageDescendants`
> Get child pages of specified page

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `pageId` (string) **(required)** — Page or blog post ID, or a Confluence tiny link ID (the encoded part from /wiki/x/ URLs, e.g., Fc1bBw)
  - `limit` (number) *(optional)* — Max descendants
  - `depth` (number) *(optional)* — Max depth
  - `cursor` (string) *(optional)* — Pagination cursor

#### `getConfluenceSpaces`
> Get spaces

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `ids` (any) *(optional)* — Space IDs
  - `keys` (any) *(optional)* — Space keys
  - `type` (string) *(optional)* — Space type
  - `status` (string) *(optional)* — Space status
  - `labels` (any) *(optional)* — Space labels
  - `favourite` (boolean) *(optional)* — Favorite spaces only
  - `favoritedBy` (string) *(optional)* — User favorites
  - `expand` (any) *(optional)* — Properties to expand
  - `start` (number) *(optional)* — Start index
  - `limit` (number) *(optional)* — Max results (default: 25, max: 250)

#### `getPagesInConfluenceSpace`
> Get pages or blog posts in a space

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `spaceId` (string) **(required)** — Space ID
  - `contentType` (string) *(optional)* — Type of content: page or blog post
  - `limit` (number) *(optional)* — Max results (default: 25, max: 250)
  - `cursor` (string) *(optional)* — Pagination cursor
  - `status` (string) *(optional)* — Page status
  - `title` (string) *(optional)* — Title filter
  - `sort` (string) *(optional)* — Sort order
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `searchConfluenceUsingCql`
> Search content with CQL

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `cql` (string) **(required)** — CQL query string (e.g., "title ~ "meeting" AND type = page")
  - `cqlcontext` (string) *(optional)* — CQL context
  - `cursor` (string) *(optional)* — Pagination cursor
  - `expand` (string) *(optional)* — Properties to expand
  - `limit` (number) *(optional)* — Max results (default: 25, max: 250)
  - `prev` (boolean) *(optional)* — Include previous page link
  - `next` (boolean) *(optional)* — Include next page link

#### `updateConfluencePage`
> Update a Confluence page or blog post

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `pageId` (string) **(required)** — Page or blog post ID, or a Confluence tiny link ID (the encoded part from /wiki/x/ URLs, e.g., Fc1bBw)
  - `contentType` (string) *(optional)* — Type of content: page or blog post
  - `title` (string) *(optional)* — New title
  - `status` (string) *(optional)* — Page status
  - `spaceId` (string) *(optional)* — Space ID
  - `parentId` (string) *(optional)* — Parent page ID (pages only, ignored for blogs)
  - `body` (string) **(required)** — Page content
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.
  - `versionMessage` (string) *(optional)* — Version message
  - `includeBody` (boolean) *(optional)* — If true, include the page body in the response; if false, omit it to reduce payload size.

### Issues (13)

#### `addCommentToJiraIssue`
> Add comment

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `issueIdOrKey` (string) **(required)** — Issue ID or key (e.g., PROJ-123 or 10000)
  - `commentBody` (string) **(required)** — Comment body
  - `commentVisibility` (object) *(optional)*
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.
  - `responseContentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `addWorklogToJiraIssue`
> Add or update a worklog on a Jira issue. When worklogId is provided, updates that worklog;

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `issueIdOrKey` (string) **(required)** — Issue ID or key (e.g., PROJ-123 or 10000)
  - `timeSpent` (string) **(required)** — Time spent (e.g. 2h, 30m, 4d). Required for new worklogs; use to set or change time when updating.
  - `worklogId` (string) *(optional)* — ID of an existing worklog to update. If omitted, a new worklog is created.
  - `commentBody` (string) *(optional)* — Comment body
  - `started` (string) *(optional)* — When the work was started (ISO 8601 date-time, e.g. 2026-03-09T09:00:00.000+0000). If omitted, the worklog is booked at the current date/time.
  - `visibility` (object) *(optional)*
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `createIssueLink`
> Create a link between two Jira issues. For directional link types (e.g. Blocks): inwardIssue = issue that blocks, outwardIssue = issue that is blocked (e.g. "A is blocked by B" → inwardIssue: B,...

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `inwardIssue` (string) **(required)** — Inward issue key (e.g. HSP-1).
  - `outwardIssue` (string) **(required)** — Outward issue key (e.g. MKY-1).
  - `type` (string) **(required)** — Link type name (e.g. Duplicate, Blocks, Clones, Relates). Use getIssueLinkTypes to list available types.
  - `comment` (string) *(optional)* — Optional comment on the outward issue.
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `createJiraIssue`
> Create issue

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `projectKey` (string) **(required)** — Project key
  - `issueTypeName` (string) **(required)** — Type (Task, Bug, Story)
  - `summary` (string) **(required)**
  - `description` (string) *(optional)* — Issue description
  - `parent` (string) *(optional)* — Parent for subtasks
  - `assignee_account_id` (string) *(optional)* — Assignee ID
  - `additional_fields` (object) *(optional)* — REQUIRED for custom fields. This is the ONLY parameter to set priority, labels, custom fields, or any other Jira fields not listed above. Pass a JSON object with field names as keys. Example: {"priority": {"name": "High"}, "labels": ["bug"], "customfield_10001": "value"}.
  - `transition` (object) *(optional)* — Optional workflow transition to apply during creation. Use getTransitionsForJiraIssue to find valid transition IDs. Placed at top level of Jira API request, not inside fields.
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.
  - `responseContentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `editJiraIssue`
> Update issue

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `issueIdOrKey` (string) **(required)** — Issue ID or key (e.g., PROJ-123 or 10000)
  - `fields` (object) **(required)**
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.
  - `responseContentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `getIssueLinkTypes`
> Get available Jira issue link types (e.g. Blocks, Duplicate, Clones, Relates). For createIssueLink: inwardIssue = blocker, outwardIssue = blocked (e.g. "A is blocked by B" → inwardIssue: B,...

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)

#### `getJiraIssue`
> Get issue details

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `issueIdOrKey` (string) **(required)** — Issue ID or key (e.g., PROJ-123 or 10000)
  - `fields` (array) *(optional)*
  - `fieldsByKeys` (boolean) *(optional)*
  - `expand` (string) *(optional)*
  - `properties` (array) *(optional)*
  - `updateHistory` (boolean) *(optional)*
  - `failFast` (boolean) *(optional)*
  - `responseContentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `getJiraIssueRemoteIssueLinks`
> Get remote links

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `issueIdOrKey` (string) **(required)** — Issue ID or key (e.g., PROJ-123 or 10000)
  - `globalId` (string) *(optional)*

#### `getJiraIssueTypeMetaWithFields`
> Get field metadata

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `projectIdOrKey` (string) **(required)**
  - `issueTypeId` (string) **(required)**
  - `startAt` (number) *(optional)*
  - `maxResults` (number) *(optional)*

#### `getJiraProjectIssueTypesMetadata`
> Get issue types

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `projectIdOrKey` (string) **(required)**
  - `startAt` (number) *(optional)*
  - `maxResults` (number) *(optional)*

#### `getTransitionsForJiraIssue`
> Get transitions

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `issueIdOrKey` (string) **(required)** — Issue ID or key (e.g., PROJ-123 or 10000)
  - `expand` (string) *(optional)*
  - `transitionId` (string) *(optional)*
  - `skipRemoteOnlyCondition` (boolean) *(optional)*
  - `includeUnavailableTransitions` (boolean) *(optional)*
  - `sortByOpsBarAndStatus` (boolean) *(optional)*

#### `searchJiraIssuesUsingJql`
> Search issues with JQL

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `jql` (string) **(required)** — JQL query
  - `maxResults` (number) *(optional)* — Max (50-100)
  - `fields` (array) *(optional)*
  - `nextPageToken` (string) *(optional)* — Page token
  - `responseContentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `transitionJiraIssue`
> Transition issue status

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `issueIdOrKey` (string) **(required)** — Issue ID or key (e.g., PROJ-123 or 10000)
  - `transition` (object) **(required)**
  - `fields` (object) *(optional)*
  - `update` (object) *(optional)*
  - `historyMetadata` (object) *(optional)*

### Jira (2)

#### `getVisibleJiraProjects`
> Get projects

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `searchString` (string) *(optional)*
  - `action` (string) *(optional)*
  - `startAt` (number) *(optional)*
  - `maxResults` (number) *(optional)*
  - `expandIssueTypes` (boolean) *(optional)*

#### `lookupJiraAccountId`
> Lookup user IDs

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `searchString` (string) **(required)**

### Other (2)

#### `fetch`
> Get details of a Jira issue or Confluence page by ARI (Atlassian Resource Identifier), if the id is not an ARI, then use a different tool to fetch the content

**Parameters:**
  - `cloudId` (string) *(optional)* — Not needed for this tool — cloudId is extracted from the ARI automatically
  - `id` (string) **(required)** — Atlassian Resource Identifier (ARI) from search results, e.g., "ari:cloud:jira:cloudId:issue/10107" or "ari:cloud:confluence:cloudId:page/123456789"

#### `getAccessibleAtlassianResources`
> Get cloudId to make tool calls. When a link is provided (e.g. https://site.atlassian.net/*), try passing the site hostname (e.g. site.atlassian.net) as cloudId to other tools first; if that fails,...

### Search (1)

#### `search`
> Search Jira and Confluence using Rovo Search, ALWAYS use this tool to search for Jira and Confluence content unless the word CQL or JQL is used in the context

**Parameters:**
  - `cloudId` (string) *(optional)* — Not needed for this tool — cloudId is derived from your access token automatically
  - `query` (string) **(required)** — The search query to use for Rovo Search

### Users (6)

#### `atlassianUserInfo`
> Get current user info

#### `createConfluenceFooterComment`
> Create a footer comment on a page or blog post

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `pageId` (string) *(optional)* — Page or blog post ID, or a Confluence tiny link ID (the encoded part from /wiki/x/ URLs, e.g., Fc1bBw)
  - `contentType` (string) *(optional)* — Type of content: page or blog post
  - `parentCommentId` (string) *(optional)* — Parent comment ID for replies
  - `attachmentId` (string) *(optional)* — Attachment ID to include
  - `customContentId` (string) *(optional)* — Custom content ID to include
  - `body` (string) **(required)** — Comment content
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `createConfluenceInlineComment`
> Create an inline comment on specific text in a page or blog post

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `pageId` (string) *(optional)* — Page or blog post ID, or a Confluence tiny link ID (the encoded part from /wiki/x/ URLs, e.g., Fc1bBw)
  - `contentType` (string) *(optional)* — Type of content: page or blog post
  - `parentCommentId` (string) *(optional)* — Parent comment ID for replies
  - `body` (string) **(required)** — Comment content
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.
  - `inlineCommentProperties` (object) *(optional)* — Text selection properties for highlighting

#### `getConfluenceCommentChildren`
> Get reply(child) comments for a comment

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `commentId` (string) **(required)** — Parent comment ID
  - `commentType` (string) **(required)** — Comment type
  - `limit` (number) *(optional)* — Max replies
  - `cursor` (string) *(optional)* — Pagination cursor
  - `sort` (string) *(optional)* — Sort order
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `getConfluencePageFooterComments`
> Get footer comments for a page or blog post

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `pageId` (string) **(required)** — Page or blog post ID, or a Confluence tiny link ID (the encoded part from /wiki/x/ URLs, e.g., Fc1bBw)
  - `contentType` (string) *(optional)* — Type of content: page or blog post
  - `limit` (number) *(optional)* — Max comments
  - `cursor` (string) *(optional)* — Pagination cursor
  - `status` (string) *(optional)* — Comment status
  - `sort` (string) *(optional)* — Sort order
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

#### `getConfluencePageInlineComments`
> Get inline comments for a page or blog post

**Parameters:**
  - `cloudId` (string) **(required)** — Cloud ID (UUID or site URL)
  - `pageId` (string) **(required)** — Page or blog post ID, or a Confluence tiny link ID (the encoded part from /wiki/x/ URLs, e.g., Fc1bBw)
  - `contentType` (string) *(optional)* — Type of content: page or blog post
  - `limit` (number) *(optional)* — Max comments
  - `cursor` (string) *(optional)* — Pagination cursor
  - `status` (string) *(optional)* — Comment status
  - `resolutionStatus` (string) *(optional)* — Resolution status
  - `sort` (string) *(optional)* — Sort order
  - `contentFormat` (string) *(optional)* — Content format: "adf" (Atlassian Document Format, JSON) for full fidelity with mentions, panels, and Smart Links, or "markdown" for simplified text. Defaults to ADF when omitted.

---
