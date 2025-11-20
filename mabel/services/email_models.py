"""Email data models and validation."""

import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, field_validator, model_validator


# Simple email regex for basic validation
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')


class EmailAddress(BaseModel):
    """Represents an email address with optional display name."""

    address: str
    display_name: Optional[str] = None

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate email address format."""
        if not EMAIL_REGEX.match(v):
            raise ValueError(f"Invalid email address: {v}")
        return v

    def format(self) -> str:
        """Format as 'Display Name <address>' or just 'address'."""
        if self.display_name:
            return f"{self.display_name} <{self.address}>"
        return self.address


class EmailAttachment(BaseModel):
    """Represents an email attachment."""

    filename: str
    content_type: str
    content_base64: str

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Ensure filename is not empty."""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        return v.strip()

    @field_validator('content_base64')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError("Attachment content cannot be empty")
        return v.strip()


class EmailRequest(BaseModel):
    """
    Complete email request model.

    Validates all email parameters and ensures at least one of:
    text_body, html_body, or template is provided.
    """

    # Sender information
    from_address: Optional[str] = None
    from_name: Optional[str] = None

    # Recipients
    to: Union[str, List[str]]
    cc: Optional[Union[str, List[str]]] = None
    bcc: Optional[Union[str, List[str]]] = None

    # Subject and content
    subject: str
    text_body: Optional[str] = None
    html_body: Optional[str] = None

    # Template-based rendering
    template: Optional[str] = None
    template_vars: Optional[Dict[str, Any]] = None

    # Attachments
    attachments: Optional[List[EmailAttachment]] = None

    # Metadata for logging/tracking
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('to', 'cc', 'bcc')
    @classmethod
    def normalize_recipients(cls, v: Optional[Union[str, List[str]]]) -> List[str]:
        """Normalize recipient fields to lists."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('from_address')
    @classmethod
    def validate_from_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate from_address if provided."""
        if v is not None and not EMAIL_REGEX.match(v):
            raise ValueError(f"Invalid from_address: {v}")
        return v

    @model_validator(mode='after')
    def validate_recipients(self) -> 'EmailRequest':
        """Ensure at least one recipient in 'to' field."""
        if not self.to or len(self.to) == 0:
            raise ValueError("At least one 'to' recipient is required")

        # Validate all recipient addresses
        all_recipients = self.to + (self.cc or []) + (self.bcc or [])
        for recipient in all_recipients:
            if not EMAIL_REGEX.match(recipient):
                raise ValueError(f"Invalid recipient email address: {recipient}")

        return self

    @model_validator(mode='after')
    def validate_content(self) -> 'EmailRequest':
        """Ensure at least one content source is provided."""
        has_text = self.text_body is not None and len(self.text_body.strip()) > 0
        has_html = self.html_body is not None and len(self.html_body.strip()) > 0
        has_template = self.template is not None and len(self.template.strip()) > 0

        if not (has_text or has_html or has_template):
            raise ValueError(
                "At least one of 'text_body', 'html_body', or 'template' must be provided"
            )

        return self

    @model_validator(mode='after')
    def validate_subject(self) -> 'EmailRequest':
        """Ensure subject is not empty."""
        if not self.subject or not self.subject.strip():
            raise ValueError("Subject cannot be empty")
        return self

    def get_metadata_value(self, key: str, default: Any = None) -> Any:
        """Get a value from metadata dict."""
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)
