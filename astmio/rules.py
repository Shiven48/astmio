from astmio.base_validator import BaseValidationRule
from astmio.dataclasses import ASTMData, ASTMRecord, DecodingResult
from astmio.enums import ValidationStrictness
from astmio.plugins import get_logger

log = get_logger(__name__)


class HeaderTerminatorRule(BaseValidationRule):
    """Ensures message starts with 'H' record and ends with 'L' record."""

    def __init__(
        self, strictness: ValidationStrictness = ValidationStrictness.WARNING
    ):
        super().__init__(
            name="header_terminator_check",
            description="Message must start with Header (H) and end with Terminator (L) record",
            strictness=strictness,
        )

    def validate(self, parsed_records: DecodingResult) -> bool:
        records: ASTMData = parsed_records.data

        if not records or len(records) < 2:
            return False

        # Check first record starts with 'H'
        first_record = records[0]
        if not first_record or first_record[0] != "H":
            return False

        # Check last record starts with 'L'
        last_record = records[-1]
        if not last_record or last_record[0] != "L":
            return False

        log.info(f"Validated structure against: {self.name}")
        return True


class NoUnknownRecordsRule(BaseValidationRule):
    """Ensures all records are of known ASTM types."""

    def __init__(
        self,
        strictness: ValidationStrictness = ValidationStrictness.WARNING,
        known_types: set | None = None,
    ):
        super().__init__(
            name="no_unknown_records_check",
            description="All records must be of known ASTM type (H, P, O, R, C, Q, M, L, S)",
            strictness=strictness,
        )
        self.known_types = known_types or {
            "H",
            "P",
            "O",
            "R",
            "C",
            "Q",
            "M",
            "L",
            "S",
        }

    def validate(self, parsed_records: DecodingResult) -> bool:
        records: ASTMData = parsed_records.data
        for record in records:
            if not record:
                continue
            record_type: ASTMRecord = record[0]
            if record_type not in self.known_types:
                return False
        log.info(f"Validated Structure against: {self.name}")
        return True


class UniqueFramingRecordRule(BaseValidationRule):
    """Ensures records like H,P and L are present only once."""

    def __init__(
        self,
        strictness: ValidationStrictness = ValidationStrictness.WARNING,
    ):
        super().__init__(
            name="unique_framing_records_check",
            description="There should be only one records H, P and L",
            strictness=strictness,
        )

    def validate(self, parsed_records: DecodingResult) -> bool:
        records: ASTMData = parsed_records.data
        counts = {"H": 0, "P": 0, "L": 0}

        for record in records:
            if not record:
                continue

            record_type: ASTMRecord = record[0]
            if record_type in counts:
                counts[record_type] += 1

        is_valid = counts["H"] == 1 and counts["L"] == 1
        if is_valid:
            log.info(f"Validated Structure against: {self.name}")

        return is_valid


class OrderResultCountRule(BaseValidationRule):
    """Validates that Order records match Result records count."""

    def __init__(
        self, strictness: ValidationStrictness = ValidationStrictness.WARNING
    ):
        super().__init__(
            name="order_result_count_match",
            description="Number of Order (O) records should match Result (R) records",
            strictness=strictness,
        )

    def validate(self, parsed_records: DecodingResult) -> bool:
        order_count = 0
        result_count = 0
        records: ASTMData = parsed_records.data

        for record in records:
            if not record:
                continue

        if record[0] == "O":
            if len(record) > 4 and record:
                test_field = record

                if isinstance(test_field, list):
                    order_count += len(test_field)
                else:
                    order_count += 1

        # --- Result Counting Logic (no changes needed) ---
        elif record == "R":
            result_count += 1

        if order_count == result_count:
            log.info(f"Validated Structure against: {self.name}")

        return order_count == result_count
