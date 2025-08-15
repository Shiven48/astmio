"""
ASTM Structure Validation Framework

A simple, extensible validation system for ASTM messages that allows:
- Universal validation rules (strict enforcement)
- User-defined custom rules (configurable strictness)
- Easy registration and execution of validation logic
"""

from __future__ import annotations

from typing import Callable

from astmio.base_validator import BaseValidationRule, FunctionValidationRule
from astmio.dataclasses import DecodingResult, ParsedValidationResult
from astmio.enums import ValidationStrictness
from astmio.rules import (
    HeaderTerminatorRule,
    NoUnknownRecordsRule,
    OrderResultCountRule,
    UniqueFramingRecordRule,
)


class ValidationPipeline:
    """
    Main orchestrator for registering and executing validation rules.

    This class manages both universal (built-in) rules and user-defined custom rules,
    executing them in the correct order based on strictness levels.
    """

    def __init__(self):
        """Initialize pipeline with empty rule registry."""
        self._rules: dict[str, BaseValidationRule] = {}
        self._register_universal_rules()

    def _register_universal_rules(self):
        """Register universal validation rules that apply to all ASTM messages."""
        universal_rules: list[BaseValidationRule] = [
            HeaderTerminatorRule(strictness=ValidationStrictness.STRICT),
            NoUnknownRecordsRule(strictness=ValidationStrictness.STRICT),
            UniqueFramingRecordRule(strictness=ValidationStrictness.STRICT),
            OrderResultCountRule(strictness=ValidationStrictness.STRICT),
        ]

        for rule in universal_rules:
            self._rules[rule.name] = rule

    # This adds a rule based on class based pattern
    def register_rule(self, rule: BaseValidationRule, overwrite: bool = False):
        """
        Register a custom validation rule.

        Args:
            rule: The validation rule to register
            overwrite: Whether to overwrite existing rule with same name
        """
        if rule.name in self._rules and not overwrite:
            raise ValueError(
                f"Rule '{rule.name}' already exists. Use overwrite=True to replace."
            )

        self._rules[rule.name] = rule

    # This adds a rule based on function based pattern
    def register_function_rule(
        self,
        name: str,
        description: str,
        strictness: ValidationStrictness,
        validator_func: Callable[[DecodingResult], bool],
    ):
        """
        Register a function-based validation rule for simpler custom rules.

        Args:
            name: Unique name for the rule
            description: Human-readable description
            strictness: Whether rule failure should halt (STRICT) or warn (WARNING)
            validator_func: Function that takes parsed_records and returns bool
        """
        rule: BaseValidationRule = FunctionValidationRule(
            name, description, strictness, validator_func
        )
        self.register_rule(rule)

    def unregister_rule(self, rule_name: str):
        """Remove a rule from the pipeline."""
        if rule_name in self._rules:
            del self._rules[rule_name]

    def list_rules(self) -> dict[str, str]:
        """Get a summary of all registered rules."""
        return {
            name: f"{rule.strictness.value}: {rule.description}"
            for name, rule in self._rules.items()
        }

    def execute(self, parsed_records: DecodingResult) -> ParsedValidationResult:
        """
        Execute all registered validation rules against parsed ASTM data.

        Args:
            parsed_records: List of parsed ASTM records

        Returns:
            ValidationResult containing errors, warnings, and overall status
        """
        result = ParsedValidationResult()

        # Separate rules by strictness for proper execution order
        strict_rules: list[BaseValidationRule] = [
            rule
            for rule in self._rules.values()
            if rule.strictness == ValidationStrictness.STRICT
        ]
        warning_rules: list[BaseValidationRule] = [
            rule
            for rule in self._rules.values()
            if rule.strictness == ValidationStrictness.WARNING
        ]

        # Execute STRICT rules
        for rule in strict_rules:
            try:
                if not rule.validate(parsed_records):
                    result.add_error(
                        rule.name, f"STRICT rule failed: {rule.description}"
                    )
                    return result
            except Exception as e:
                result.add_error(
                    rule.name, f"Exception in rule '{rule.name}': {str(e)}"
                )
                return result

        # Execute WARNING rules
        for rule in warning_rules:
            try:
                if not rule.validate(parsed_records):
                    result.add_warning(
                        rule.name, f"Warning: {rule.description}"
                    )
            except Exception as e:
                result.add_warning(
                    rule.name,
                    f"Exception in warning rule '{rule.name}': {str(e)}",
                )

        return result


class ValidationPipelineFactory:
    """Factory to create pre-configured pipelines for common use cases."""

    @staticmethod
    def create_standard_pipeline() -> ValidationPipeline:
        """Create pipeline with standard rules (mixed strictness levels)."""
        return ValidationPipeline()  # Already has universal rules

    @staticmethod
    def create_strict_pipeline() -> ValidationPipeline:
        """Create pipeline where most rules are strict."""
        pipeline = ValidationPipeline()
        pipeline.register_rule(
            OrderResultCountRule(strictness=ValidationStrictness.STRICT),
            overwrite=True,
        )
        return pipeline

    @staticmethod
    def create_lenient_pipeline() -> ValidationPipeline:
        """Create pipeline with minimal strict rules."""
        pipeline = ValidationPipeline()
        return pipeline
