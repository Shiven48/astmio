from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from astmio.plugins.logging import get_logger

from .exceptions import ConfigurationError
from .field_mapper import DiscriminatedField

log = get_logger(__name__)

# --- Pydantic Models ---


# Transport Specific Config models
class BaseNetworkConfig(BaseModel):
    """Base configuration for network-based transports (TCP/UDP)."""

    host: str = "0.0.0.0"
    port: int = Field(default=15200, ge=1, le=65535)
    timeout: float = Field(default=30.0, gt=0)
    encoding: str = "ascii"
    control_chars: Dict[str, int] = Field(default_factory=dict)


class SerialConfig(BaseModel):
    """Configuration for serial port communication."""

    port: str
    mode: Literal["serial"] = "serial"
    baudrate: int = 9600
    databits: int = 8
    parity: Optional[str] = None
    stopbits: int = 1
    timeout: float = Field(default=10.0, gt=0)

    @field_validator("port")
    def validate_port(cls, v: str) -> str:
        if not v:
            raise ConfigurationError(
                message="Serial port name cannot be empty.",
                config_key="port",
                config_value=v,
            )
        return v

    @field_validator("baudrate")
    def validate_baudrate(cls, v: int) -> int:
        standard_rates = {
            300,
            600,
            1200,
            2400,
            4800,
            9600,
            19200,
            38400,
            57600,
            115200,
        }
        if v not in standard_rates:
            log.warning(
                f"Unusual baud rate configured: {v}. Ensure the device supports it."
            )
        return v

    @field_validator("databits")
    def validate_databits(cls, v: int) -> int:
        if v not in [5, 6, 7, 8]:
            raise ConfigurationError(
                message="Invalid data bits. Must be one of: 5, 6, 7, 8.",
                config_key="databits",
                config_value=v,
            )
        return v

    @field_validator("stopbits")
    def validate_stopbits(cls, v: int) -> int:
        if v not in [1, 2]:
            raise ConfigurationError(
                message="Invalid stop bits. Must be 1 or 2.",
                config_key="stopbits",
                config_value=v,
            )
        return v

    @field_validator("parity")
    def validate_parity(cls, v: Optional[str]) -> Optional[str]:
        valid = {"NONE", "EVEN", "ODD", "MARK", "SPACE"}
        if v and v.upper() not in valid:
            raise ConfigurationError(
                message=f"Invalid parity '{v}'. Must be one of: {sorted(valid)}.",
                config_key="parity",
                config_value=v,
            )
        return v.upper() if v else v


class TCPConfig(BaseNetworkConfig):
    """Configuration for TCP transport, including SSL options."""

    mode: Literal["tcp"] = "tcp"
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    max_connections: int = Field(default=10, gt=0)

    @model_validator(mode="before")
    def validate_tcp_config(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate TCP-specific settings, like SSL dependencies."""
        if data.get("ssl_enabled"):
            if not data.get("ssl_cert_path"):
                raise ConfigurationError(
                    message="When SSL is enabled, 'ssl_cert_path' is required.",
                    config_key="ssl_cert_path",
                    config_value=data.get("ssl_cert_path"),
                )
            if not data.get("ssl_key_path"):
                raise ConfigurationError(
                    message="When SSL is enabled, 'ssl_key_path' is required.",
                    config_key="ssl_key_path",
                    config_value=data.get("ssl_key_path"),
                )
        return data


class UDPConfig(BaseNetworkConfig):
    """Configuration for UDP transport."""

    mode: Literal["udp"] = "udp"


class ConnectionConfig(BaseModel):
    """
    Configuration for ASTM connections, implemented as a Pydantic model
    for robust validation.
    """

    host: str = "localhost"
    port: int = Field(default=15200, ge=1, le=65535)
    timeout: float = Field(default=10.0, gt=0)
    encoding: str = "latin-1"
    chunk_size: Optional[int] = None
    max_retries: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, gt=0)
    keepalive: bool = True
    device_profile: Optional[str] = None

    @field_validator("chunk_size")
    def validate_chunk_size(cls, v: Optional[int]) -> Optional[int]:
        """Ensure chunk_size is a positive integer if it is not None."""
        if v is not None and v <= 0:
            raise ValueError(
                "chunk_size must be a positive integer if provided."
            )
        return v

    def __str__(self) -> str:
        return f"ConnectionConfig(host={self.host}, port={self.port})"

    def __repr__(self) -> str:
        return (
            f"ConnectionConfig(host={self.host!r}, port={self.port}, "
            f"timeout={self.timeout}, encoding={self.encoding!r})"
        )


class RecordConfig(BaseModel):
    """
    A Pydantic model that validates the configuration for a single record type
    (e.g., the 'H' record or 'P' record) from the YAML file.
    """

    record_type: str
    description: Optional[str] = None
    total_fields: Optional[int] = Field(None, gt=0)
    repeated: bool = False
    fields: List[DiscriminatedField] = []
    validation_rules: Dict[str, Any] = {}
    custom_parser: Optional[str] = None
    ignored_fields_index: List[int] = []

    @field_validator("fields", mode="before")
    @classmethod
    def assign_astm_positions(
        cls, fields_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Pre-processes the raw field data before validation.
        1. Renames the 'type' key from YAML to 'field_type' for our discriminator.
        2. Injects the astm_position based on list order.
        """
        for i, field_config in enumerate(fields_data):
            if isinstance(field_config, dict):
                if "type" in field_config:
                    field_config["field_type"] = field_config.pop("type")

                # Logic from your existing validator to set position
                if "astm_position" not in field_config:
                    field_config["astm_position"] = i + 1
        return fields_data

    @model_validator(mode="after")
    def validate_record_logic(self) -> "RecordConfig":
        """
        A post-validator that checks for consistency and correctness across the
        entire list of fields after they have all been individually parsed.
        """
        # Check for duplicate field names within this record
        names: List[str] = [field.field_name for field in self.fields]
        if len(names) != len(set(names)):
            seen = set()
            duplicates = {n for n in names if n in seen or seen.add(n)}
            raise ConfigurationError(
                message=f"Duplicate field names found in record configuration: {sorted(duplicates)}",
                config_key="fields",
            )

        # Check that there is at least one field marked as required
        if not any(field.required for field in self.fields):
            log.warning(
                "Configuration warning: Record type '%s' has no fields marked as 'required: true'. "
                "This may make the record difficult to use for data validation.",
                self.record_type,
            )

        # Check if total_fields (if specified) matches the actual number of fields
        if (
            self.total_fields is not None
            and len(self.fields) != self.total_fields
        ):
            log.warning(
                "Configuration mismatch: The record is defined with 'total_fields' of %s, "
                "but contains %s fields.",
                self.total_fields,
                len(self.fields),
            )

        return self


# parser Specific Config models
class ChecksumConfig(BaseModel):
    """Configuration for checksum handling."""

    has_checksums: bool = False
    checksum_position: Optional[str] = None
    checksum_size: Optional[int] = None

    @model_validator(mode="after")
    def validate_checksum_logic(self) -> "ChecksumConfig":
        # If checksum is enable then checksum_position and checksum_size is must
        if self.has_checksums:
            if self.checksum_position is None:
                raise ConfigurationError(
                    message="If 'has_checksums' is true, 'checksum_position' must be specified",
                    config_key="parser.checksum.checksum_position",
                )

            if self.checksum_size is None or self.checksum_size <= 0:
                raise ConfigurationError(
                    message="If 'has_checksums' is true, 'checksum_size' must be a positive integer.",
                    config_key="parser.checksum.checksum_size",
                )
        else:
            if self.checksum_position is not None:
                log.warning(
                    f"Configuration warning: 'checksum_position' ({self.checksum_position}) is provided but 'has_checksums' is false. This value will be ignored."
                )
            if self.checksum_size is not None:
                log.warning(
                    f"Configuration warning: 'checksum_size' ({self.checksum_size}) is provided but 'has_checksums' is false. This value will be ignored."
                )
        return self


class SequenceNoConfig(BaseModel):
    """Configuration for sequence number handling."""

    has_sequence_numbers: bool = False
    has_multiple_sequence_numbers: bool = False
    is_chunked: bool = False

    @model_validator(mode="after")
    def validate_sequence_logic(self) -> "SequenceNoConfig":
        if self.is_chunked and not self.has_sequence_numbers:
            raise ConfigurationError(
                message="If 'is_chunked' is true, 'has_sequence_numbers' must also be true.",
                config_key="parser.sequence_no.is_chunked",
                config_value=self.is_chunked,
            )
        return self


class TerminatorConfig(BaseModel):
    """Configuration for message terminators."""

    record_termination: Literal["CR", "LF", "CRLF"] = "CR"
    frame_termination: Literal["ETX", "ETB", "EOT"] = "ETX"
    message_termination: Literal[
        "CRLF", "EOT", "ETX"
    ] = "CRLF"  # EOT is common for full message termination


class ParserConfig(BaseModel):
    """
    Comprehensive configuration for the ASTM parser, derived from the YAML.
    """

    strict: bool = False
    repeated_components: List[str] = Field(default_factory=list)
    valid_special_chars: List[
        Literal["STX", "ETX", "CR", "LF", "ETB", "CRLF", "EOT"]
    ] = Field(default_factory=lambda: ["STX", "ETX", "CR", "LF", "ETB", "CRLF"])
    checksum: ChecksumConfig = Field(default_factory=ChecksumConfig)
    sequence_no: SequenceNoConfig = Field(default_factory=SequenceNoConfig)
    terminator: TerminatorConfig = Field(default_factory=TerminatorConfig)
    # delimiters: DelimitersConfig = Field(default_factory=DelimitersConfig)

    @model_validator(mode="after")
    def validate_parser_logic(self) -> "ParserConfig":
        if (
            self.sequence_no.has_sequence_numbers
            and self.terminator.frame_termination not in ["ETX", "ETB"]
        ):
            log.warning(
                "Configuration warning: 'has_sequence_numbers' is true, but 'frame_termination' is not ETX or ETB. "
                "This might lead to parsing issues for multi-frame messages."
            )
        if self.strict and not self.checksum.has_checksums:
            log.warning(
                "Configuration warning: 'strict' is true, but 'there is no checksum'. "
                "This will lead the parser to throw an error."
            )
        return self


__all__ = [
    "BaseNetworkConfig",
    "SerialConfig",
    "TCPConfig",
    "UDPConfig",
    "ConnectionConfig",
    "RecordConfig",
    "ChecksumConfig",
    "SequenceNoConfig",
    "TerminatorConfig",
    "ParserConfig",
]
