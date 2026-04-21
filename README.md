# MockGenerator

Automatically generates CMocka mocks for C unit tests from GCC/CMake linker errors.

## Requirements

- Python 3.8+ (no external dependencies)

## Setup

Create `mockgenerator.ini` in the same directory as `main.py`:

```ini
[project]
cmake_root = C:/Projects/MyProject/Code

# optional, this is the default
test_cmake_lists = tests/CMakeLists.txt

# path to the tests directory, relative to cmake_root (default: tests)
tests_root = tests

[search]
# multiple entries: indent each additional line
exclude_dirs =
    autosar/generated
    vendor/lowlevel

# CMake variables used in include paths (e.g. ${Variant})
[cmake_vars]
Variant = VariantA

[output]
# mode: "file" = write to .txt | "inplace" = inject directly into test file
mode = file
output_dir = mocks_out
test_file_prefixes =
    TestUnit_
    TestIntegration_

# Regex patterns for the mock section boundaries (inplace mode only)
# mock_section_start = @defgroup.*Mocks
# mock_section_end = ^\s*/\*\*
```

## Usage

1. Run the CMake/make build and save the error output to a file
2. Run the tool:

```
python main.py build_output.log
```

Generated mocks are written to `mocks_out/build_output_mocks.txt`.

For direct injection into the test file:

```
python main.py build_output.log --inplace
```

Use `-v` / `--verbose` for detailed output.

## Inplace Mode Requirements

Two conditions must be met for `--inplace` to work on a test file:

**1. Test file naming**

The build log line must contain the test file's basename (e.g. `TestUnit_ComponentA.c`), and that name must start with one of the configured prefixes:

```ini
[output]
test_file_prefixes =
    TestUnit_
    TestIntegration_
```

The tool searches for a matching file anywhere under `tests_root`. Files whose basename does not start with a configured prefix are silently skipped.

**2. Mock section markers**

The tool locates the mock section using two configurable regex patterns:

| Option | Default | Matches |
|--------|---------|---------|
| `mock_section_start` | `@defgroup.*Mocks` | Line that opens the mock section |
| `mock_section_end` | `^\s*/\*\*` | First line after the start that ends the section |

Mocks are injected immediately before the line matching `mock_section_end`. If no end marker is found, mocks are appended at the end of the file. If the start marker is missing entirely, the tool prints an error and skips that file.

Default layout (Doxygen `@defgroup` style):

```c
/**
 * @defgroup UnitTest_MyModule_Mock Mocks
 * @{
 */

/* generated mocks are inserted here */

/**                                        <-- mock_section_end matches here
 * @defgroup UnitTest_MyModule_Tests Test Cases
 * @{
 */
```

Alternative layout using explicit comment markers:

```c
/* Start of generated mocks */

/* generated mocks are inserted here */

/* End of generated mocks */               <-- mock_section_end matches here
```

```ini
[output]
mock_section_start = /\* Start of generated mocks \*/
mock_section_end = /\* End of generated mocks \*/
```

## Output Format

### Functions

```c
// void return, no parameters
void Foo_Reset(void)
{
    function_called();
}

// non-void return + parameters
Std_ReturnType Foo_Read(uint8 Index, P2VAR(uint8, AUTOMATIC, DATA) BufferPtr)
{
    check_expected(Index);
    check_expected_ptr(BufferPtr);
    return mock();
}
```

### Variables

```c
uint8 Foo_StatusVariable = {0}; /* MOCK: verify initial value */
```

### Unresolved symbols

Symbols not found in any header appear as a comment placeholder:

```c
/* MOCK: the following symbols could not be resolved - handle manually: */
/* SomeUnknownSymbol */
```

## Notes

- Include paths are read from `tests/CMakeLists.txt`
- Paths listed in CMakeLists.txt that do not exist on disk are reported as warnings
- AUTOSAR compiler abstraction macros (`FUNC()`, `P2VAR()`, `P2CONST()` etc.) are supported
- Already mocked symbols are detected and skipped on repeated runs (inplace mode)
