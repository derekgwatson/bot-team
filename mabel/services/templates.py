"""Email template loading and rendering with Jinja2."""

from pathlib import Path
from typing import Dict, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class TemplateError(Exception):
    """Raised when template operations fail."""
    pass


class EmailTemplateRenderer:
    """
    Handles loading and rendering of email templates.

    Templates are stored in templates/emails/ and can be:
    - {template_name}.txt.j2 for plain text
    - {template_name}.html.j2 for HTML
    - Both (for multipart emails)
    """

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        """
        Initialize the template renderer.

        Args:
            template_dir: Directory containing email templates.
                         If None, uses templates/emails/ relative to mabel root.
        """
        if template_dir is None:
            # Default to templates/emails/ in the mabel directory
            mabel_root = Path(__file__).parent.parent
            template_dir = mabel_root / "templates" / "emails"

        if not template_dir.exists():
            raise TemplateError(f"Template directory does not exist: {template_dir}")

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,  # Auto-escape for security
            trim_blocks=True,
            lstrip_blocks=True
        )

    def render_email_template(
        self,
        template_name: str,
        context: Dict
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Render an email template.

        Looks for {template_name}.txt.j2 and {template_name}.html.j2.
        Returns (text_body, html_body) tuple.

        Args:
            template_name: Name of the template (without extension)
            context: Dictionary of variables to pass to the template

        Returns:
            Tuple of (text_body, html_body). Either may be None if that
            template variant doesn't exist.

        Raises:
            TemplateError: If both .txt.j2 and .html.j2 are missing,
                          or if rendering fails.
        """
        text_template_name = f"{template_name}.txt.j2"
        html_template_name = f"{template_name}.html.j2"

        text_body: Optional[str] = None
        html_body: Optional[str] = None

        # Try to load and render text template
        try:
            text_template = self.env.get_template(text_template_name)
            text_body = text_template.render(context)
        except TemplateNotFound:
            # Text template is optional
            pass
        except Exception as e:
            raise TemplateError(f"Error rendering text template '{text_template_name}': {e}")

        # Try to load and render HTML template
        try:
            html_template = self.env.get_template(html_template_name)
            html_body = html_template.render(context)
        except TemplateNotFound:
            # HTML template is optional
            pass
        except Exception as e:
            raise TemplateError(f"Error rendering HTML template '{html_template_name}': {e}")

        # At least one must exist
        if text_body is None and html_body is None:
            raise TemplateError(
                f"Template '{template_name}' not found. "
                f"Expected {text_template_name} or {html_template_name} "
                f"in {self.template_dir}"
            )

        return text_body, html_body

    def template_exists(self, template_name: str) -> bool:
        """
        Check if a template exists (either .txt.j2 or .html.j2).

        Args:
            template_name: Name of the template (without extension)

        Returns:
            True if at least one variant exists, False otherwise
        """
        text_exists = (self.template_dir / f"{template_name}.txt.j2").exists()
        html_exists = (self.template_dir / f"{template_name}.html.j2").exists()
        return text_exists or html_exists


# Singleton instance (initialized when needed)
_renderer: Optional[EmailTemplateRenderer] = None


def get_renderer(template_dir: Optional[Path] = None) -> EmailTemplateRenderer:
    """
    Get or create the global template renderer instance.

    Args:
        template_dir: Optional template directory (only used on first call)

    Returns:
        EmailTemplateRenderer instance
    """
    global _renderer
    if _renderer is None:
        _renderer = EmailTemplateRenderer(template_dir)
    return _renderer


def render_email_template(
    template_name: str,
    context: Dict
) -> Tuple[Optional[str], Optional[str]]:
    """
    Convenience function to render a template using the global renderer.

    Args:
        template_name: Name of the template (without extension)
        context: Dictionary of variables to pass to the template

    Returns:
        Tuple of (text_body, html_body)

    Raises:
        TemplateError: If template is missing or rendering fails
    """
    renderer = get_renderer()
    return renderer.render_email_template(template_name, context)
