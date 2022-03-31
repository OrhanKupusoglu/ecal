"""
Filter compilation database so that undesired CPP and H files are excluded from clang-tidy's output.
Its default configuration file is 'excludes_clang_tidy.json'.

This script processes the 'compile_commands.json' file which CMake can generate since v2.8.5.
`JSON Compilation Database Format Specification <https://clang.llvm.org/docs/JSONCompilationDatabase.html>`__

The CPP files which are located in the directories given by 'excludes_clang_tidy.json' are filtered out.
The filtering results in two JSON files, one for included and one for excluded commands.
H files located in this directories are included as '-isystem' instead of '-I',
so that they are excluded from static analysis as well.
"""

import argparse
import json
import os
import sys

# ------------------------------------------------------------------------------

DEBUG = False
TERMINATE_OK = False
REPLACE_WITH_SYSTEM_HEADERS = True
DEF_BUILD='../../_build'
DEF_CONFIG='excludes_clang_tidy.json'

path_config = ''
path_build = ''
path_relative = ''
commands = []
excludes = []
commands_inc = []
commands_exc = []

# ------------------------------------------------------------------------------

def read_args():
    """
    Parse arguments with the 'argparse' module:
    `argparse — Parser for command-line options, arguments and sub-commands <https://docs.python.org/3/library/argparse.html>`__
    Check help with '-h|--help'.
    """
    global path_config
    global path_build
    global path_relative

    # display default values
    parser = argparse.ArgumentParser(description='Filter compilation database.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--build',
                        help='rel/abs path of the build directory',
                        default=DEF_BUILD)
    parser.add_argument('--config',
                        help='rel/abs path of the config JSON file',
                        default=DEF_CONFIG)

    args = parser.parse_args()
    build = args.build
    config = args.config

    if DEBUG:
        print(f'arg :: build  = "{build}"')
        print(f'arg :: config = "{config}"')

    # change first working directory to script's directory
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
    path_relative = os.getcwd()

    if os.path.isabs(build):
        path_build = build
    else:
        path_build = os.path.realpath(os.path.join(path_relative, build))

    if os.path.isabs(config):
        path_config = config
    else:
        path_config = os.path.realpath(os.path.join(path_relative, config))

def read_config():
    """
    Read the configuration file for excluded directories.
    Each member of the array itself is an array of directory names.
    These names are concatenated into proper subdirectory parts.
    These strings are then searched for in the commands array.
    """
    global excludes

    if not os.path.exists(path_config):
        if TERMINATE_OK:
            print('ERROR - Directory exclusion configuration is missing, skipping further processing')
            sys.exit(0)
        else:
            raise SystemExit(f'** FATAL - file to list excluded directories is missing:\n{path_config}')

    with open(path_config, 'r') as excludes_file:
        excludes_raw = json.load(excludes_file)

    # The excludes_raw list contains each excluded directory name as a list,
    # so that a proper platform-dependent string can be obtained easily.
    # The 'directory' string starts artificially with path separator to prevent partial matches.
    for exclude_raw in excludes_raw:
        exclude = os.path.sep + os.path.sep.join(exclude_raw)
        excludes.append(exclude)

    if DEBUG:
        print('EXCLUDED DIRECTORIES:')
        print(json.dumps(excludes, indent = 4, ensure_ascii=False, sort_keys=False))

def read_commands():
    """
    Read the 'compile_commands.json' file generated by CMake.
    """
    global commands

    path_database = os.path.join(path_build, 'compile_commands.json')
    if not os.path.exists(path_database):
        if TERMINATE_OK:
            print('ERROR - CMake-generated file "compile_commands.json" is missing, skipping further processing')
            sys.exit(0)
        else:
            raise SystemExit(f'** FATAL - file to list compile commands is missing:\n{path_database}')

    with open(path_database, 'r') as cmake_gen_file:
        commands = json.load(cmake_gen_file)

    if DEBUG:
        print('COMPILE COMMANDS:')
        print(json.dumps(commands, indent = 4, ensure_ascii=False, sort_keys=False))

def filter_sources():
    """
    In the commands array, using the excluded directory strings, the 'file' key is used to filter the commands.
    Therefore the JSON array is separated into two JSON arrays.
    """
    for command in commands:
        if DEBUG:
            print(command['file'])
        # use relative path to remove the common part of the path to increase speed & reliability
        # path string starts artificially with path separator to prevent partial matches
        path_str = os.path.sep + os.path.relpath(os.path.dirname(command['file']), path_relative)
        include_folder = True
        for exclude in excludes:
            if exclude in path_str:
                include_folder = False
                break

        if include_folder:
            if DEBUG:
                print('++ included')
            commands_inc.append(command)
        else:
            if DEBUG:
                print('-- excluded')
            commands_exc.append(command)

def filter_headers():
    """
    Clang-tidy scans headers with "HeaderFilterRegex: '.*' configuration more deeply.
    Although theoretically it is possible to use CMake facilities, a pragmatic solution
    to undesired header processing is to replace plain includes with system includes.
    During the static analysis system headers are ignored unless stated otherwise.
    """
    if REPLACE_WITH_SYSTEM_HEADERS:
        # strip the leading path separator
        for index, value in enumerate(excludes):
            excludes[index] = value.lstrip(os.path.sep)
        for command in commands_inc:
            for exclude in excludes:
                exclude_path = os.path.join(path_relative, exclude)
                header_include = f'-I{exclude_path}'
                header_system = f'-isystem {exclude_path}'
                if header_include in command['command']:
                    if DEBUG:
                        print(f"-- {command['command']}")
                    command['command'] = command['command'].replace(header_include, header_system)
                    if DEBUG:
                        print(f"++ {command['command']}")

def save_commands():
    """
    Save two JSON files, one for included and one for excluded commands.
    Line counts of these files must match the original commands, minus the extra '[' and ']' lines.
    """

    PATH_COMPILE_COMMANDS_INC = os.path.join(path_build, 'compile_commands_inc.json')
    PATH_COMPILE_COMMANDS_EXC = os.path.join(path_build, 'compile_commands_exc.json')

    with open(PATH_COMPILE_COMMANDS_INC, 'w') as commands_inc_json:
        json.dump(commands_inc, commands_inc_json, indent=4, ensure_ascii=False, sort_keys=False)

    with open(PATH_COMPILE_COMMANDS_EXC, 'w') as commands_exc_json:
        json.dump(commands_exc, commands_exc_json, indent=4, ensure_ascii=False, sort_keys=False)

def main():
    read_args()
    read_config()
    read_commands()
    filter_sources()
    filter_headers()
    save_commands()

if __name__ == '__main__':
    main()
