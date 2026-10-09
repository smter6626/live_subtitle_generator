#!/usr/bin/env python3
"""REL1B status/integrate/resume. Production requires separately deployed trust."""
from __future__ import annotations

import argparse
import os
import sys

from release_approval import Policy, Stop, authorize, require
from release_integration import Integration, audit_git, check_source, clean, git, tools
from release_journal import Journal


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's usual message repeats caller-controlled secrets/invalid JSON.
        self.exit(2, 'release-controller: INPUT_INVALID\n')


def build_parser():
    parser = Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('command', choices=('status', 'integrate', 'resume'))
    return parser


def status(policy: Policy):
    auth = authorize(policy)
    check_source(auth)
    value = Journal(auth).inspect()
    if value is None:
        return 'MISSING'
    clone = auth.managed / 'clone'
    if os.path.lexists(clone):
        # Local read-only commands only: no fetch, merge-tree, bootstrap or hooks.
        audit_git(clone, auth.payload['origin'])
        clean(clone)
        if value['merge_commit'] is not None:
            require(git(clone, 'rev-parse', 'HEAD') == value['merge_commit'] and
                    git(clone, 'show', '-s', '--format=%P', 'HEAD') ==
                    auth.payload['main'] + ' ' + auth.payload['accepted_commit'] and
                    git(clone, 'rev-parse', 'HEAD^{tree}') == value['merge_tree'], 'JOURNAL_FACTS')
            tools(clone, auth)
    else:
        require(value['state'] == 'NEW', 'PERSISTENCE_INCOMPLETE')
    Journal(auth).validate_logs(value)
    return value['state'] + '_RECORDED_UNVERIFIED'


def _run(argv, policy: Policy, *, fixture_gate=None, checkpoint=None):
    """Isolated harness calls the same argparse/pipeline, with no CLI overrides."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == 'status':
            phase = status(policy)
        else:
            value = Integration(policy, fixture_gate=fixture_gate, checkpoint=checkpoint).execute()
            phase = value['state'] + '_AWAITING_INDEPENDENT_REVIEW'
        print('release-controller: ' + phase)
        return 0
    except Stop as exc:
        print('release-controller: STOP ' + exc.code, file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        print('release-controller: STOP OPERATION_FAILED', file=sys.stderr)
        return 1


def main(argv=None):
    return _run(sys.argv[1:] if argv is None else argv, Policy())


if __name__ == '__main__':
    raise SystemExit(main())
