from abc import ABC, abstractmethod
from typing import Callable

from astmio.dataclasses import ParsedValidationResult
from astmio.enums import ValidationStrictness


class BaseValidationRule(ABC):
    """
    Abstract base class for all validation rules.

    Each rule is self-contained with its own name, description,
    strictness level, and validation logic.
    """

    def __init__(
        self, name: str, description: str, strictness: ValidationStrictness
    ):
        self.name = name
        self.description = description
        self.strictness = strictness

    @abstractmethod
    def validate(self, parsed_records: ParsedValidationResult) -> bool:
        """
        Core validation logic - must be implemented by subclasses.

        Args:
            parsed_records: List of parsed ASTM records

        Returns:
            True if validation passes, False otherwise
        """
        pass


class FunctionValidationRule(BaseValidationRule):
    """Wrapper to convert simple functions into validation rules."""

    def __init__(
        self,
        name: str,
        description: str,
        strictness: ValidationStrictness,
        validator_func: Callable[[ParsedValidationResult], bool],
    ):
        super().__init__(name, description, strictness)
        self.validator_func = validator_func

    def validate(self, parsed_records: ParsedValidationResult) -> bool:
        return self.validator_func(parsed_records)
