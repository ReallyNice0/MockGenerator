# MockGenerator

Automatische Generierung von CMocka-Mocks für C-Unit-Tests aus GCC/CMake Linker-Fehlern.

## Voraussetzungen

- Python 3.8+ (keine weiteren Abhängigkeiten)

## Setup

`mockgenerator.ini` im selben Verzeichnis wie `main.py` anlegen:

```ini
[project]
cmake_root = C:/Projects/MyProject/Code

# optional, das ist der Default
test_cmake_lists = tests/CMakeLists.txt

[search]
# mehrere Einträge: jede weitere Zeile einrücken
exclude_dirs =
    autosar/generated
    vendor/lowlevel

[output]
output_dir = mocks_out
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
