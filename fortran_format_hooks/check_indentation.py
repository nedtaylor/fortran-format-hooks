import os
import re
import sys
import glob
import argparse
from typing import Optional, Sequence

## Attribution statement:
##  Some of the functionality in this file is based on the pre-commit/pre-commit-hooks repository
##  https://github.com/pre-commit/pre-commit-hooks/blob/main/pre_commit_hooks


# Function to fix the indentation of the file
# Copied from pre-commit/pre-commit-hooks repository
# https://github.com/pre-commit/pre-commit-hooks/blob/main/pre_commit_hooks/pretty_format_json.py
def _autofix(filename: str, new_contents: str) -> None:
    print(f'Fixing file {filename}')
    with open(filename, 'w', encoding='UTF-8') as f:
        f.write(new_contents)

def check_if_match(actual_indent, expected_indent, continued_indent, continuation_line, line_num, file_path):
    if continuation_line:
        if actual_indent != continued_indent:
            print(f"Indentation error in {file_path}, line {line_num}: "
                f"Expected {continued_indent} spaces, found {actual_indent}")
            return False
    else:
        if actual_indent != expected_indent:
            print(f"Indentation error in {file_path}, line {line_num}: "
                f"Expected {expected_indent} spaces, found {actual_indent}")
            return False
    return True

def correct_lines(corrected_lines, stripped_line, expected_indent, continuation_line, continued_indent):
    if continuation_line:
        corrected_lines.append( " " * continued_indent + stripped_line.lstrip() )
    else:
        corrected_lines.append( " " * expected_indent + stripped_line.lstrip() )

def strip_quoted_sections(line, in_single_quote=False, in_double_quote=False):
    result = []
    i = 0
    quote_char = None

    while i < len(line):
        char = line[i]

        if not in_single_quote and not in_double_quote:
            if char == "'":
                in_single_quote = True
                quote_char = "'"
                i += 1
                continue
            elif char == '"':
                in_double_quote = True
                quote_char = '"'
                i += 1
                continue
            else:
                result.append(char)
        elif in_single_quote:
            if char == "'" and (i + 1 >= len(line) or line[i + 1] != "'"):
                in_single_quote = False
                quote_char = None
            elif char == "'" and line[i + 1] == "'":  # Escaped quote
                i += 1  # skip next quote
        elif in_double_quote:
            if char == '"' and (i + 1 >= len(line) or line[i + 1] != '"'):
                in_double_quote = False
                quote_char = None
            elif char == '"' and line[i + 1] == '"':  # Escaped quote
                i += 1  # skip next quote
        i += 1

    return ''.join(result), in_single_quote, in_double_quote

def check_indentation(file_path, line_length=80, relaxed_line_margin=0.1):
    corrected_lines = []
    procedure_indent = 2
    module_program_indent = 2
    loop_conditional_indent = 3
    continuation_indent = 5

    inside_module_program = False
    procedure_depth = 0
    inside_loop_conditional = False
    inside_select = False
    specifier_line = False
    inside_derived_type = False
    on_continued_if_line = False
    on_continued_loop_line = False
    on_continued_case_line = False
    inside_procedure_arguments = False
    inside_associate_arguments = False
    inside_do_concurrent_limits = False
    interface_block = False

    readwrite_argument_line = False
    readwrite_statement_line = False

    expected_indent = 0  # Default expected indentation
    continuation_line = False  # Flag to indicate if the previous line was a continuation
    open_bracket_count = 0  # Count of unbalanced open brackets
    close_bracket_count = 0  # Count of unbalanced close brackets
    unbalanced_brackets = 0
    continued_indent = 0
    num_single_quotes = 0
    num_double_quotes = 0
    unbalanced_quotes = False
    equality_depth = 0
    equality_brackets = []
    in_single_quote = False
    in_double_quote = False

    success = True

    relaxed_line_length = int(line_length * relaxed_line_margin)

    with open(file_path, 'r') as file:
        for line_num, line in enumerate(file, start=1):
            
            

            # Be more relaxed with comment lines regarding line length (using PEP8, flake8-bugbear, B950)
            # https://stackoverflow.com/questions/46863890/does-pythons-pep8-line-length-limit-apply-to-comments
            if re.match(r'^\s*!', line):
                if len(line) > line_length + 1 + relaxed_line_length:
                    print(f"Comment Line {line_num} in {file_path} exceeds {line_length} characters: {len(line) - 1}")
            # check length of line does not exceed
            elif len(line) > line_length + 1:
                if len(line) > line_length + 1 + relaxed_line_length:
                    print(f"Line {line_num} in {file_path} exceeds hard limit {line_length + relaxed_line_length} characters: {len(line) - 1}")
                    success = False
                else:
                    print(f"Note: Line {line_num} in {file_path} exceeds {line_length} characters: {len(line) - 1}, but within 10% of limit")

            stripped_line = line.rstrip()

            # Skip empty lines
            if not stripped_line:
                continuation_line = False
                corrected_lines.append("")
                continue

            # If comment line !###, skip
            if re.match(r'^\s*!###', stripped_line):
                corrected_lines.append(stripped_line)
                continue

            # Check if preprocessing directive
            if re.match(r'^\s*#', stripped_line):
                corrected_lines.append(stripped_line)
                continue

            # Check for lines with ! in first column and skip
            if re.match(r'^!', stripped_line):
                corrected_lines.append(stripped_line)
                continue

            # Replace all numbers at the start of the line with the same number of spaces
            stripped_line = re.sub(r'^\d+', lambda x: ' ' * len(x.group()), stripped_line)

            # Check if line starts with comment
            if re.match(r'^\s*!', stripped_line):
                actual_indent = len(stripped_line) - len(stripped_line.lstrip())
                if not check_if_match(actual_indent, expected_indent, continued_indent, continuation_line, line_num, file_path):
                    success = False
                    # return False, None
                correct_lines(corrected_lines, stripped_line, expected_indent, continuation_line, continued_indent)
                continue

            # If inside a quoted section, check if line starts with ampersand
            if in_single_quote or in_double_quote:
                if not re.match(r'^\s*&', stripped_line):
                    print(f"Unbalanced quotes in {file_path}, line {line_num}")
                    print(stripped_line)
                    return False, None

            # Remove quoted sections from this line
            stripped_line_excld_quote, in_single_quote, in_double_quote = strip_quoted_sections(
                stripped_line,
                in_single_quote=in_single_quote,
                in_double_quote=in_double_quote
            )

            # Check if line starts with close bracket, if so, update the indentation
            if re.match(r'^\s*(\)|/\)|\])', stripped_line): #stripped_line_excld_quote):
                continued_indent = expected_indent + ( unbalanced_brackets - 1 ) * continuation_indent + equality_depth * continuation_indent
                if readwrite_statement_line:
                    continued_indent += continuation_indent

            # Count open and close brackets
            open_bracket_count += stripped_line_excld_quote.count('(')
            open_bracket_count += stripped_line_excld_quote.count('[')
            close_bracket_count += stripped_line_excld_quote.count(')')
            close_bracket_count += stripped_line_excld_quote.count(']')
            if readwrite_argument_line and re.match(r'^\s*(\)|/\)|\])', stripped_line_excld_quote):
                readwrite_argument_line = False
                readwrite_statement_line = True
            if stripped_line_excld_quote.count('(') + stripped_line_excld_quote.count('[') < \
                    stripped_line_excld_quote.count(')') + stripped_line_excld_quote.count(']'):
                unbalanced_brackets -= 1
            elif stripped_line_excld_quote.count('(') + stripped_line_excld_quote.count('[') > \
                    stripped_line_excld_quote.count(')') + stripped_line_excld_quote.count(']'):
                unbalanced_brackets += 1


            # Detect end of do loop, if statement, or where statement
            if re.match(r'^\s*end\s*(do|if|where|select)\b', stripped_line, re.IGNORECASE):
                expected_indent -= loop_conditional_indent

            # Detect else statements in if and where blocks, can be "PATTERN", "PATTERN\s*if", or "PATTERN\s*where"
            if inside_loop_conditional and re.match(r'^\s*else\s*(if|where)?\b', stripped_line, re.IGNORECASE):
                prior_indent = expected_indent
                expected_indent -= loop_conditional_indent
                specifier_line = True


            # Detect case, type, and rank statements within select, can be "PATTERN(", "PATTERN (" or "PATTERN default"
            if ( inside_select and re.match(r'^\s*(case|class is|type is|rank)\s*\(', stripped_line, re.IGNORECASE) ) or \
               ( inside_select and re.match(r'^\s*(case|class|rank)\s+default\b', stripped_line, re.IGNORECASE) ):
                prior_indent = expected_indent
                expected_indent -= loop_conditional_indent
                specifier_line = True

            # Detect if contains line
            if re.match(r'^\s*contains\b', stripped_line, re.IGNORECASE):
                prior_indent = expected_indent
                specifier_line = True
                if inside_derived_type:
                    expected_indent -= loop_conditional_indent - 1
                else:
                    expected_indent -= module_program_indent

            # Detect end of block block
            if re.match(r'^\s*end\s*block\b', stripped_line, re.IGNORECASE):
                expected_indent -= procedure_indent

            # Detect end of associate block
            if re.match(r'^\s*end\s*associate\b', stripped_line, re.IGNORECASE):
                expected_indent -= loop_conditional_indent

            # Detect end of interface block
            if re.match(r'^\s*end\s*interface\b', stripped_line, re.IGNORECASE):
                interface_block = False
                expected_indent -= loop_conditional_indent

            # Detect end of derived type block
            if inside_derived_type and re.match(r'^\s*end\s*type\b', stripped_line, re.IGNORECASE):
                expected_indent -= loop_conditional_indent
                inside_derived_type = False

            # Detect end of procedure block
            if procedure_depth > 0 and re.match(r'^\s*end\s*(function|subroutine|procedure)\b', stripped_line, re.IGNORECASE):
                expected_indent -= procedure_indent
                procedure_depth -= 1

            # Detect end of module or program
            if re.match(r'^\s*end\s*(submodule|module|program)\b', stripped_line, re.IGNORECASE):
                expected_indent -= module_program_indent



            #-----------------------------------------------------------------------------------------------
            # Check actual indentation
            #-----------------------------------------------------------------------------------------------
            actual_indent = len(stripped_line) - len(stripped_line.lstrip())
            correct_lines(corrected_lines, stripped_line, expected_indent, continuation_line, continued_indent)
            if not check_if_match(actual_indent, expected_indent, continued_indent, continuation_line, line_num, file_path):
                success = False
                # return False, None
            #-----------------------------------------------------------------------------------------------
            

            # strip comments from end of line
            stripped_line = re.sub(r'!.*', '', stripped_line).strip()

            # Check if entering an equality statement
            if equality_depth > 0:
                if not stripped_line.endswith('&'):
                    equality_depth = 0
                elif equality_brackets[-1] > unbalanced_brackets:
                    equality_depth -=1
                    equality_brackets.pop()
                elif re.search(r',\s*&$', stripped_line) and equality_brackets[-1] == unbalanced_brackets:
                    equality_depth -= 1
                    equality_brackets.pop()
            if equality_depth == 0:
                equality_brackets = []

            # Check if line ends with "&" and has = as the last non-whitespace character before "&"
            if continuation_line:
                if stripped_line.endswith("&") and re.search(r'=\s*&$', stripped_line):
                    equality_depth += 1
                    equality_brackets.append(unbalanced_brackets)

            # Calculate expected indentation for continuation line
            if continuation_line:
                continued_indent = expected_indent + unbalanced_brackets * continuation_indent + equality_depth * continuation_indent
                if readwrite_statement_line:
                    continued_indent += continuation_indent

            # Check for line continuation character
            if stripped_line.endswith('&'):
                if not continuation_line:
                    continuation_line = True
                    # Set expected indentation for next line
                    continued_indent = expected_indent + continuation_indent
                    if unbalanced_brackets == 0:
                        unbalanced_brackets = 1
            else:
                # If it was a continuation line, reset to normal expected indentation
                if in_single_quote or in_double_quote:
                    print(f"Unbalanced quotes in {file_path}, line {line_num}")
                    return False, None
                open_bracket_count = 0
                close_bracket_count = 0
                unbalanced_brackets = 0
                if continuation_line:
                    continuation_line = False
                if inside_procedure_arguments:
                    inside_procedure_arguments = False
                    expected_indent += procedure_indent
                if inside_associate_arguments:
                    inside_associate_arguments = False
                    expected_indent += loop_conditional_indent
                if readwrite_argument_line:
                    readwrite_argument_line = False
                if readwrite_statement_line:
                    readwrite_statement_line = False
                    

            # Reset from contains line
            if not continuation_line and specifier_line:
                specifier_line = False
                expected_indent = prior_indent
            

            # Detect module or program blocks (specifically avoid module procedure/function)
            if re.match(r'^\s*module\b(?!\s+(recursive|procedure|function|subroutine))', stripped_line, re.IGNORECASE) or \
                re.match(r'^\s*(submodule|program)\b', stripped_line, re.IGNORECASE):
                expected_indent += module_program_indent

            # Detect procedure blocks, can be "module (function|subroutine|procedure)" or "(function|subroutine|procedure)" but not "procedure(", "procedure," or "procedure ::"
            if re.match(r'^\s*(integer\s+|logical\s+)?(elemental\s+|recursive\s+|pure\s+)?(module\s+)?(recursive\s+)?(function|subroutine|procedure)\b', stripped_line, re.IGNORECASE) and \
                not re.match(r'^\s*(function|subroutine|procedure)\s*(,|::)', stripped_line, re.IGNORECASE) and \
                not re.match(r'^\s*procedure\s*(\(|\,)', stripped_line, re.IGNORECASE): # and \
                # not ( interface_block and re.match(r'^(?!\s*procedure\s+\w+\s*\()', stripped_line, re.IGNORECASE) ):
                if not ( interface_block and re.match(r'^\s*(module\s+)?procedure\b', stripped_line, re.IGNORECASE) ):
                    # print(stripped_line)
                    # print("INTERFACE BLOCK: ", interface_block)
                    # print(re.match(r'^\s*(integer\s+)', stripped_line, re.IGNORECASE), stripped_line)
                    procedure_depth += 1
                    if stripped_line.lower().endswith("&"):
                        inside_procedure_arguments = True
                    else:
                        expected_indent += procedure_indent


            # Detect derived type block
            if re.match(r'^\s*type\s*(::|,)', stripped_line, re.IGNORECASE):
                expected_indent += loop_conditional_indent
                inside_derived_type = True

            # Detect interface block, can be "abstract interface" or "interface"
            if re.match(r'^\s*(abstract\s+)?interface\b', stripped_line, re.IGNORECASE):
                interface_block = True
                expected_indent += loop_conditional_indent

            # Detect associate block
            if re.match(r'^\s*associate\b', stripped_line, re.IGNORECASE):
                if stripped_line.lower().endswith("&"):
                    inside_associate_arguments = True
                else:
                    expected_indent += loop_conditional_indent
            
            # Detect block block
            if re.match(r'^\s*\w+\s*:\s*block\b', stripped_line, re.IGNORECASE) or \
               re.match(r'^\s*block\b', stripped_line, re.IGNORECASE):
                expected_indent += procedure_indent

            # Detect do loop, and where statement with optional "NAME:"
            if re.match(r'^\s*\w+\s*:\s*(do|where)\b', stripped_line, re.IGNORECASE) or \
               re.match(r'^\s*(do|where)\b', stripped_line, re.IGNORECASE):
                if stripped_line.lower().endswith("&"):
                    on_continued_loop_line = True
                else:
                    expected_indent += loop_conditional_indent
                    inside_loop_conditional = True

            # Detect do concurrent linebreak statement with optional "NAME:"
            if re.match(r'^\s*\w+\s*:\s*do\s+concurrent\b', stripped_line, re.IGNORECASE) or \
               re.match(r'^\s*do\s+concurrent\b', stripped_line, re.IGNORECASE):
                inside_do_concurrent_limits = True
                # expected_indent -= loop_conditional_indent
                inside_loop_conditional = False
            
            if inside_do_concurrent_limits and not continuation_line:
                # if stripped_line.lower().endswith(")"):
                #     expected_indent += loop_conditional_indent
                inside_do_concurrent_limits = False
                inside_loop_conditional = True


            # Detect "if RANDOM then" statement with optional "NAME:"
            if re.match(r'^\s*\w*\s*:\s*if\s*\(.*\)\s*then\b', stripped_line, re.IGNORECASE) or \
               re.match(r'^\s*if\s*\(.*\)\s*then\b', stripped_line, re.IGNORECASE):
                expected_indent += loop_conditional_indent
                inside_loop_conditional = True

            # Detect line ends with "then" from unfinished if statement 
            if on_continued_if_line and not continuation_line:
                if stripped_line.lower().endswith("then"):
                    expected_indent += loop_conditional_indent
                on_continued_if_line = False

            # Detect end of continued case line
            if on_continued_case_line and not continuation_line:
                expected_indent += loop_conditional_indent
                on_continued_case_line = False

            # Detect end of continued loop line
            if on_continued_loop_line and not continuation_line:
                expected_indent += loop_conditional_indent
                on_continued_loop_line = False

            # Detect if linebreak statement with optional "NAME:"
            if continuation_line and \
               ( re.match(r'^\s*\w+\s*:\s*(if)\b', stripped_line, re.IGNORECASE) or \
                 re.match(r'^\s*(if)\b', stripped_line, re.IGNORECASE) ):
                on_continued_if_line = True

            # Detect select type, select case, and select rank
            if re.match(r'^\s*(?:\w+\s*:\s*)?select\s+(type|case|rank)\b', stripped_line, re.IGNORECASE):
                if stripped_line.lower().endswith("&"):
                    on_continued_case_line = True
                else:
                    expected_indent += loop_conditional_indent
                    inside_select = True

            # Detect read/write statement
            if re.match(r'^\s*(read|write)\s*\(', stripped_line, re.IGNORECASE) and stripped_line.lower().endswith("&"):
                if unbalanced_brackets == 0:
                    readwrite_statement_line = True
                else:
                    readwrite_argument_line = True


    # if not present, add blank line to end of file
    if corrected_lines[-1].strip():
        corrected_lines.append("")
    return success, "\n".join(corrected_lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Code copied form https://github.com/pre-commit/pre-commit-hooks/blob/main/pre_commit_hooks/check_added_large_files.py
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'filenames', nargs='*',
        help='Filenames pre-commit believes are changed.',
    )
    parser.add_argument(
        '--line-length', type=int, default=80,
        help='Maximum line length.',
    )
    parser.add_argument(
        '--relaxed-line-margin', type=float, default=0.1,
        help='Leniency for line length check (0.1 = 10%).',
    )
    parser.add_argument(
        '--autofix',
        action='store_true',
        dest='autofix',
        help='Automatically fixes encountered indentation errors.',
    )
    ## add option to ignore filepath patterns
    parser.add_argument(
        '--ignore-patterns',
        dest='ignore_patterns',
        nargs='*',
        help='Ignore files that match these patterns.',
    )
    ## add option to ignore specified directories
    parser.add_argument(
        '--ignore-directories',
        dest='ignore_directories',
        nargs='*',
        help='Ignore files in these directories.',
    )
    args = parser.parse_args(argv)

    success = True
    for filename in args.filenames:
        skip_file = False
        ## only apply if .f90 or .F90 file
        if not filename.endswith('.f90') and not filename.endswith('.F90'):
            continue
        ## check if file matches ignore patterns
        if args.ignore_patterns:
            for pattern in args.ignore_patterns:
                if re.match(pattern, filename):
                    skip_file = True
                    print(f"Skipping file {filename} because it matches the ignore pattern {pattern}.")
                    break
        ## check if file is in ignore directories
        if args.ignore_directories:
            for directory in args.ignore_directories:
                if directory in filename:
                    skip_file = True
                    break
        if skip_file:
            print(f"Skipping file {filename} because it is in an ignored directory.")
            continue
        success, corrected_code = check_indentation(filename, args.line_length, args.relaxed_line_margin)
        # if not check_indentation(filename, args.line_length):
        #     success = 1
        if success:
            print(f"{filename} passed indentation check.")
        else:
            print(f"{filename} failed indentation check.")
            if args.autofix:
                _autofix(filename, corrected_code)
 
    return 0 if success else 1

if __name__ == "__main__":
    raise SystemExit(main())
