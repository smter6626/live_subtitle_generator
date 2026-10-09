#!/usr/bin/env python3
"""Prompt-authorized local release workflow; normal native Git/gh login."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from release_approval import LightweightPolicy, Stop, authorize_workflow, require
from release_integration import Integration, native_authentication
import release_pipeline
import release_workflow

COMMANDS = ('status', 'integrate', 'prepare', 'resume', 'human-gate', 'publish')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'release-lightweight: STOP ARGUMENTS_INVALID\n')


def run(command, policy):
    require(type(policy) is LightweightPolicy and command in COMMANDS, 'ARGUMENTS_INVALID')
    # Authorize before native authentication, restore the transport context even
    # after KeyboardInterrupt. Legacy entry points never select this mode.
    authorize_workflow(policy)
    with native_authentication(policy):
        if command == 'integrate':
            Integration(policy).execute()
            return 'FINAL_MAIN_REVIEW_REQUIRED'
        function = {'status': release_pipeline.status, 'prepare': release_pipeline.prepare,
                    'resume': release_pipeline.resume, 'human-gate': release_workflow.human_gate,
                    'publish': release_pipeline.publish}[command]
        return function(policy)


def main(argv=None):
    parser = Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--approval', type=Path, required=True,
                        help='ordinary 0600 local decision record; not a signing key')
    parser.add_argument('command', choices=COMMANDS)
    args = parser.parse_args(argv)
    try:
        result = run(args.command, LightweightPolicy(args.approval))
        print('release-lightweight: ' + result)
        return 0
    except Stop as exc:
        print('release-lightweight: STOP ' + exc.code, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('release-lightweight: STOP INTERRUPTED', file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError):
        print('release-lightweight: STOP OPERATION_FAILED', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
