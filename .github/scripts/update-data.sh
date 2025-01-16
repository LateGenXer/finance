#!/bin/sh

set -eux

export GIT_AUTHOR_NAME="LateGenXer"
export GIT_AUTHOR_EMAIL="127238994+LateGenXer@users.noreply.github.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

files="data/dmo_issued.csv data/tidm.csv"

git diff --exit-code -- $files

python3 -m data.dmo_issued
python3 -m data.tidm

if ! git diff --exit-code -- $files
then
	for file in $files
	do
		if ! git diff --exit-code -- $file
		then
			git commit -m "Update $file." -- $file
		fi
	done
	if [ "${CI:-false}" = "true" ]
	then
		git push
	else
		git push --dry-run
	fi
fi
