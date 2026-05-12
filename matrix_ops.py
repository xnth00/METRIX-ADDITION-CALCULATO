"""
matrix_ops.py
-------------
Pure matrix math functions. No Flask, no database — just logic.

Keeping this file separate makes it easy to:
  - Test the math without running the web server
  - Add new operations later (subtraction, multiplication, etc.)
  - Let your groupmates read the math logic without scrolling past web stuff
"""

# Maximum allowed matrix size. The frontend already limits to 8x8,
# but we double-check on the backend so users can't bypass it.
MAX_ROWS = 8
MAX_COLS = 8


def validate_matrix(matrix, name="Matrix"):
    """
    Check that 'matrix' is a proper 2D list of numbers.

    Returns a tuple: (is_valid, error_message)
        - is_valid: True if the matrix is okay, False otherwise
        - error_message: empty string if valid, otherwise a friendly message
    """
    # Must be a list
    if not isinstance(matrix, list):
        return False, f"{name} must be a list of rows."

    # Must not be empty
    if len(matrix) == 0:
        return False, f"{name} is empty."

    # Size limit check
    if len(matrix) > MAX_ROWS:
        return False, f"{name} has too many rows (max {MAX_ROWS})."

    # Check every row
    expected_column_count = len(matrix[0]) if isinstance(matrix[0], list) else 0

    if expected_column_count == 0:
        return False, f"{name} has no columns."

    if expected_column_count > MAX_COLS:
        return False, f"{name} has too many columns (max {MAX_COLS})."

    for row_index, row in enumerate(matrix):
        # Each row must be a list
        if not isinstance(row, list):
            return False, f"{name} row {row_index + 1} is not a list."

        # All rows must have the same number of columns
        if len(row) != expected_column_count:
            return (
                False,
                f"{name} has uneven rows: row {row_index + 1} has "
                f"{len(row)} values but should have {expected_column_count}.",
            )

        # Every cell must be a number
        for col_index, value in enumerate(row):
            # bool is a subclass of int in Python, but True/False as numbers is confusing
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return (
                    False,
                    f"{name} has a non-number at row {row_index + 1}, "
                    f"column {col_index + 1}.",
                )

    return True, ""


def same_dimensions(matrix_a, matrix_b):
    """Return True if the two matrices have the same number of rows and columns."""
    if len(matrix_a) != len(matrix_b):
        return False
    if len(matrix_a[0]) != len(matrix_b[0]):
        return False
    return True


def add_matrices(matrix_a, matrix_b):
    """
    Add two matrices and return the result.

    Raises ValueError with a clear message if anything is wrong.
    This way the calling code can just catch ValueError and show the message.
    """
    # Step 1: validate Matrix A
    is_valid_a, error_a = validate_matrix(matrix_a, "Matrix A")
    if not is_valid_a:
        raise ValueError(error_a)

    # Step 2: validate Matrix B
    is_valid_b, error_b = validate_matrix(matrix_b, "Matrix B")
    if not is_valid_b:
        raise ValueError(error_b)

    # Step 3: dimensions must match for addition
    if not same_dimensions(matrix_a, matrix_b):
        raise ValueError(
            f"Dimension mismatch: Matrix A is {len(matrix_a)}x{len(matrix_a[0])}, "
            f"Matrix B is {len(matrix_b)}x{len(matrix_b[0])}. "
            f"Both matrices must have the same dimensions for addition."
        )

    # Step 4: perform addition element by element
    rows = len(matrix_a)
    cols = len(matrix_a[0])
    result = []

    for row_index in range(rows):
        new_row = []
        for col_index in range(cols):
            sum_value = matrix_a[row_index][col_index] + matrix_b[row_index][col_index]
            new_row.append(sum_value)
        result.append(new_row)

    return result


def build_steps(matrix_a, matrix_b, result):
    """
    Build a structured step-by-step breakdown of a matrix addition.

    For each cell position (row, col), we record:
      - the value from Matrix A
      - the value from Matrix B
      - the result value
      - the position label ("R1 C2", etc.)

    This is returned as a 2D list that mirrors the matrix shape, so the
    frontend can render it cell-by-cell in a grid that matches the matrices.

    Example for a 2x2:
        [
          [
            {"row": 0, "col": 0, "label": "R1 C1", "a": 1.0, "b": 4.0, "sum": 5.0},
            {"row": 0, "col": 1, "label": "R1 C2", "a": 2.0, "b": 3.0, "sum": 5.0},
          ],
          [
            {"row": 1, "col": 0, "label": "R2 C1", "a": 7.0, "b": 2.0, "sum": 9.0},
            {"row": 1, "col": 1, "label": "R2 C2", "a": 8.0, "b": 1.0, "sum": 9.0},
          ]
        ]
    """
    steps = []
    for row_index in range(len(matrix_a)):
        row_steps = []
        for col_index in range(len(matrix_a[0])):
            a_val = matrix_a[row_index][col_index]
            b_val = matrix_b[row_index][col_index]
            sum_val = result[row_index][col_index]

            # Format numbers cleanly: whole numbers show without decimal,
            # decimals show up to 4 significant figures.
            def fmt(v):
                if v == int(v):
                    return int(v)
                return round(v, 4)

            row_steps.append({
                "row":   row_index,
                "col":   col_index,
                "label": f"R{row_index + 1} C{col_index + 1}",
                "a":     fmt(a_val),
                "b":     fmt(b_val),
                "sum":   fmt(sum_val),
            })
        steps.append(row_steps)
    return steps


def parse_matrix_from_input(raw_matrix, name="Matrix"):
    """
    Convert raw input (from the frontend) into a clean 2D list of numbers.

    The frontend sends values as strings or numbers in JSON. We convert each
    cell to a float, treating empty strings as 0 (matches the JS behavior).

    Returns the cleaned matrix. Raises ValueError if any cell can't be a number.
    """
    if not isinstance(raw_matrix, list):
        raise ValueError(f"{name} must be a 2D list.")

    cleaned = []
    for row_index, row in enumerate(raw_matrix):
        if not isinstance(row, list):
            raise ValueError(f"{name} row {row_index + 1} is not a list.")

        cleaned_row = []
        for col_index, value in enumerate(row):
            # Empty string or None -> 0 (user left the cell blank)
            if value == "" or value is None:
                cleaned_row.append(0.0)
                continue

            # Try to convert to a number
            try:
                cleaned_row.append(float(value))
            except (TypeError, ValueError):
                raise ValueError(
                    f"{name} has an invalid value '{value}' at "
                    f"row {row_index + 1}, column {col_index + 1}. "
                    f"Please enter numbers only."
                )
        cleaned.append(cleaned_row)

    return cleaned


# ---------------------------------------------------------------------------
# Quick self-test: run `python matrix_ops.py` to verify the math works.
# This block only runs when you execute this file directly, not when imported.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Running matrix_ops self-tests...\n")

    # Test 1: basic 2x2 addition
    a = [[1, 2], [3, 4]]
    b = [[5, 6], [7, 8]]
    result = add_matrices(a, b)
    print(f"Test 1 — basic addition: {result}")
    assert result == [[6, 8], [10, 12]], "Basic addition failed"

    # Test 2: dimension mismatch should raise
    try:
        add_matrices([[1, 2]], [[1], [2]])
        print("Test 2 FAILED — no error raised for mismatched dimensions")
    except ValueError as e:
        print(f"Test 2 — mismatch caught: {e}")

    # Test 3: non-number should raise
    try:
        add_matrices([["hello", 2]], [[1, 2]])
        print("Test 3 FAILED — no error raised for non-number")
    except ValueError as e:
        print(f"Test 3 — non-number caught: {e}")

    # Test 4: parse input with empty strings
    parsed = parse_matrix_from_input([["1", "", "3.5"], ["4", "5", "6"]])
    print(f"Test 4 — parsed input: {parsed}")
    assert parsed == [[1.0, 0.0, 3.5], [4.0, 5.0, 6.0]], "Parse failed"

    print("\nAll tests passed!")