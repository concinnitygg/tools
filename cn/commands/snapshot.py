"""snapshot: copy the checkout as it stands, to A/B a change against.

Take one before changing code; `ab --base NAME` builds and runs it as the
baseline. Taking a name again refreshes it.
"""

from .. import common, repo, snapshot

NAME = "snapshot"


def add_parser(sub):
    parser = sub.add_parser(NAME, help="snapshot the checkout as an A/B baseline", description=__doc__)
    parser.add_argument("name", help="the snapshot's name")
    common.add_repo(parser)
    parser.set_defaults(run=run)


def run(opts):
    snapshot.take(repo.root(opts.repo), opts.name)
