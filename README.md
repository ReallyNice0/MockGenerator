# MockGenerator

Automatische Generierung von CMocka-Mocks für C-Unit-Tests aus GCC/CMake Linker-Fehlern.

## Voraussetzungen

- Python 3.8+

```
pip install -r requirements.txt
```

## Setup

`mockgenerator.toml` im selben Verzeichnis wie `main.py` anlegen:

```toml
[project]
cmake_root = "C:/Projects/MyProject/Code"
test_cmake_lists = "tests/CMakeLists.txt"  # optional, das ist der Default

[search]
exclude_dirs = [
    "autosar/generated",   # generierter AUTOSAR-Code
    "vendor/lowlevel",     # Vendor-Libraries
]

[output]
output_dir = "mocks_out"
```

## Verwendung

1. CMake/make Build ausführen, Fehler-Output in eine Datei speichern
2. Tool aufrufen:

```
python main.py build_output.log
```

Die generierten Mocks landen in `mocks_out/build_output_mocks.txt`.

## Output-Format

### Funktionen

```c
// void/void
void Foo_Reset(void)
{
    function_called();
}

// non-void return + Parameter
Std_ReturnType Foo_Read(uint8 Index, P2VAR(uint8, AUTOMATIC, DATA) BufferPtr)
{
    check_expected(Index);
    check_expected_ptr(BufferPtr);
    return mock();
}
```

### Variablen

```c
uint8 Foo_StatusVariable = {0}; /* MOCK: verify initial value */
```

### Nicht auflösbare Symbole

Symbole die in keinem Header gefunden wurden erscheinen als Kommentar:

```c
/* MOCK: the following symbols could not be resolved - handle manually: */
/* SomeUnknownSymbol */
```

## Hinweise

- Relevante Include-Pfade werden aus `tests/CMakeLists.txt` gelesen
- Pfade die in der CMakeLists.txt stehen aber nicht existieren werden als WARNING ausgegeben
- AUTOSAR Compiler-Abstraktions-Makros (`FUNC()`, `P2VAR()`, `P2CONST()` etc.) werden unterstützt
