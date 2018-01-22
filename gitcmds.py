"""This module contains functions which invoke git cli commands."""

import re

from collections import defaultdict
from subprocess import check_output


def _trim_hash(commit):
    """Trim a commit hash to 8 characters."""

    return commit[:8]


def get_latest_commit():
    """Get the hash of the most recent commit.

    Returns
    -------
    hash : str
        The 8 character hash of the most recent commit
    """

    bash_cmd = 'git log -1 --pretty=format:"%H"'

    stdout = check_output(bash_cmd.split()).decode('utf-8').rstrip('\n')

    # single line outputs get quoted by check_output for some reason
    stdout = stdout.replace('"', '')

    return _trim_hash(stdout)


def get_git_log(commit=None):
    """Get the git log entry for one or more commits.

    This will return log entries with the format generated by the '--stat'
    option.

    Parameters
    ----------
    commit : str, optional
        The hash of the commit to get log entries for. If not given this will
        return log entries for all commits.

    Returns
    -------
    logstr : str
        A single string containing the output of a git log command.`

    """

    if commit is not None:
        bash_cmd = 'git log --stat --no-pager -1 {commit}'.format(commit=commit)
    else:
        bash_cmd = 'git log --stat --no-pager'

    stdout = check_output(bash_cmd.split()).decode('utf-8').rstrip('\n')

    return stdout


    """Get the filename(s) of files which were modified by a specific commit.

    Parameters
    ----------
    commit_hash: str
        The hash of a commit.

    Returns
    -------
    filenames: list(str)
        A list of the filenames which were modified by the specified commit.
    """

    commit_hash = _trim_hash(commit_hash)

    bash_cmd = ('git --no-pager diff {commit_hash} {commit_hash}^ --name-only'
                .format(commit_hash=commit_hash))

    cp = check_output(bash_cmd.split()).decode('utf-8').rstrip('\n')

    filenames = cp.split('\n')

    if not isinstance(filenames, list):
        filenames = [filenames]

    return filenames


def get_commit_lines(commit_hash, filenames):
    """Get the line numbers which were modified in each file by a given commit.

    Parameters
    ----------
    commit_hash: str
        The hash of a commit.
    filenames: list(str)
        A list of the filenames which were modified by the specified commit.

    Returns
    -------
    fname_lines: dict{str: list}
        A dictionary keyed on filename and valued with a list of
        (start_line, number_of_lines) tuples.
    """

    commit_hash = _trim_hash(commit_hash)
    fname_lines = defaultdict(lambda: [])

    for fname in filenames:

        bash_cmd = ('git --no-pager diff {commit}^ {commit} -U0 -- {fname}'
                    .format(commit=commit_hash, fname=fname))

        cp = check_output(bash_cmd.split()).decode('utf-8').rstrip('\n')

        # pull out the header line of each diff section
        headers = [l for l in cp.split('\n') if '@@' in l]

        # header will look like @@ -198,2 +198,2 @@
        for header in headers:

            # the .group(1) bit will pull out the part prefixed by '+'
            match = re.match('@@ -(.*) +(.*) @@', header).group(1)

            # header looks like @@ -198 +198 @@ if only one line changes
            if ',' in match:
                start, n_lines = match.split(',')
            else:
                start, n_lines = match, '1'

            if int(n_lines) > 0:
                fname_lines[fname].append((start, n_lines))

    return fname_lines


def get_blame_commit(commit_hash, filenames, fname_lines):
    """Get the commits which last touched the lines changed by a given commit.

    Parameters
    ----------
    commit_hash: str
        The hash of a commit.
    filenames: list(str)
        A list of the filenames which were modified by the specified commit.
    fname_lines: dict{str: list}
        A dictionary keyed on filename and valued with a list of
        (start_line, number_of_lines) tuples.

    Returns
    -------
    buggy_commits: set
        A set containing the hashes of the commits which last modified the
        lines modified by the given commit.
    """

    commit_hash = _trim_hash(commit_hash)
    buggy_commits = set()

    for fname in filenames:

        for start, n_lines in fname_lines[fname]:

            bash_cmd = \
                ('git --no-pager blame -L{start},+{n} {commit}^ -- {fname}'
                 .format(start=start,
                         n=n_lines,
                         commit=commit_hash,
                         fname=fname))

            cp = check_output(bash_cmd.split()).decode('utf-8').rstrip('\n')

            changed_lines = cp.split('\n')
            buggy_commits = \
                buggy_commits.union([l.split(' ')[0] for l in changed_lines])

    return buggy_commits


def link_bugs_to_commits(fix_commits):
    """Link a bugfix commit to the commits which introduced the bug it fixes.

    Parameters
    ----------
    fix_commits: list(str)
        A list of hashes for commits which fix bugs.

    Returns
    -------
    bug_commits: dict{str: list}
        A dictionary keyed on bugfix commit hash and valued with a list of
        commits which last modified the lines the bugfix commit is changing.
    """

    bug_commits = {}

    for commit in fix_commits:

        # trim the hash to 8 characters
        commit = _trim_hash(commit)

        # get the files modified by the commit
        filenames = get_commit_filenames(commit)

        # get the lines in each file modified by the commit
        fname_lines = get_commit_lines(commit, filenames)

        # get the last commit to modify those lines
        origin_commits = get_blame_commit(commit, filenames, fname_lines)

        bug_commits[commit] = origin_commits

    return bug_commits
