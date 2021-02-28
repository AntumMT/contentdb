# ContentDB
# Copyright (C) 2018-21  rubenwardy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import contextlib, git, gitdb, os, shutil, tempfile
from urllib.parse import urlsplit
from git import GitCommandError

from app.tasks import TaskError
from app.utils import randomString

def generateGitURL(urlstr):
	scheme, netloc, path, query, frag = urlsplit(urlstr)

	return "http://:@" + netloc + path + query


@contextlib.contextmanager
def get_temp_dir():
	temp = os.path.join(tempfile.gettempdir(), randomString(10))
	yield temp
	shutil.rmtree(temp)


# Clones a repo from an unvalidated URL.
# Returns a tuple of path and repo on sucess.
# Throws `TaskError` on failure.
# Caller is responsible for deleting returned directory.
@contextlib.contextmanager
def clone_repo(urlstr, ref=None, recursive=False):
	gitDir = os.path.join(tempfile.gettempdir(), randomString(10))

	err = None
	try:
		gitUrl = generateGitURL(urlstr)
		print("Cloning from " + gitUrl)

		if ref is None:
			repo = git.Repo.clone_from(gitUrl, gitDir,
					progress=None, env=None, depth=1, recursive=recursive, kill_after_timeout=15)
		else:
			assert ref != ""

			repo = git.Repo.init(gitDir)
			origin = repo.create_remote("origin", url=gitUrl)
			assert origin.exists()
			origin.fetch()
			repo.git.checkout(ref)

			for submodule in repo.submodules:
				submodule.update(init=True)

		yield repo
		shutil.rmtree(gitDir)
		return

	except GitCommandError as e:
		# This is needed to stop the backtrace being weird
		err = e.stderr

	except gitdb.exc.BadName as e:
		err = "Unable to find the reference " + (ref or "?") + "\n" + e.stderr

	raise TaskError(err.replace("stderr: ", "") \
			.replace("Cloning into '" + gitDir + "'...", "") \
			.strip())


def get_default_branch(git_url):
	git_url = generateGitURL(git_url)

	g = git.cmd.Git()

	remote_refs = {}
	for ref in g.ls_remote(git_url).split('\n'):
		hash_ref_list = ref.split('\t')
		remote_refs[hash_ref_list[1]] = hash_ref_list[0]

	hash = remote_refs.get("HEAD")
	matching = []
	for ref, value in remote_refs.items():
		if value == hash and ref != "HEAD":
			matching.append(ref)

	if len(matching) == 1:
		return matching[0].replace("refs/heads/", "")
	elif len(matching) == 0 or "master" in matching:
		return "master"
	elif "main" in matching:
		return "main"
	else:
		return matching[0].replace("refs/heads/", "")


def get_latest_commit(git_url, ref_name=None):
	git_url = generateGitURL(git_url)

	if ref_name:
		ref_name = "refs/heads/" + ref_name
	else:
		ref_name = "HEAD"

	g = git.cmd.Git()

	remote_refs = {}
	for ref in g.ls_remote(git_url).split('\n'):
		hash_ref_list = ref.split('\t')
		remote_refs[hash_ref_list[1]] = hash_ref_list[0]

	return remote_refs.get(ref_name)


def get_latest_tag(git_url):
	with get_temp_dir() as git_dir:
		repo = git.Repo.init(git_dir)
		origin = repo.create_remote("origin", url=git_url)
		origin.fetch()

		refs = repo.git.ls_remote(tags=True, sort="creatordate").split('\n')
		refs = [ref for ref in refs if ref.strip() != ""]
		if len(refs) == 0:
			return None, None

		last_ref = refs[-1]
		hash_ref_list = last_ref.split('\t')

		tag = hash_ref_list[1].replace("refs/tags/", "")
		commit_hash = repo.git.rev_parse(tag + "^{}")
		return tag, commit_hash
