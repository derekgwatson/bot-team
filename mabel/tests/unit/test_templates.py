"""Unit tests for template loading and rendering."""

import tempfile
from pathlib import Path

import pytest

from services.templates import EmailTemplateRenderer, TemplateError, render_email_template


@pytest.fixture
def temp_template_dir(tmp_path):
    """Create a temporary template directory with test templates."""
    template_dir = tmp_path / "emails"
    template_dir.mkdir()

    # Create text template
    text_template = template_dir / "test_template.txt.j2"
    text_template.write_text("Hello {{ name }}!\nWelcome to {{ service }}.")

    # Create HTML template
    html_template = template_dir / "test_template.html.j2"
    html_template.write_text("<p>Hello {{ name }}!</p><p>Welcome to {{ service }}.</p>")

    # Create text-only template
    text_only = template_dir / "text_only.txt.j2"
    text_only.write_text("Text only: {{ message }}")

    # Create HTML-only template
    html_only = template_dir / "html_only.html.j2"
    html_only.write_text("<p>HTML only: {{ message }}</p>")

    return template_dir


class TestEmailTemplateRenderer:
    """Test EmailTemplateRenderer class."""

    def test_initialization(self, temp_template_dir):
        """Test renderer initialization."""
        renderer = EmailTemplateRenderer(temp_template_dir)
        assert renderer.template_dir == temp_template_dir
        assert renderer.env is not None

    def test_initialization_with_nonexistent_dir(self):
        """Test initialization with nonexistent directory fails."""
        with pytest.raises(TemplateError) as exc_info:
            EmailTemplateRenderer(Path("/nonexistent/path"))
        assert "does not exist" in str(exc_info.value)

    def test_render_template_with_both_variants(self, temp_template_dir):
        """Test rendering template that has both text and HTML variants."""
        renderer = EmailTemplateRenderer(temp_template_dir)
        context = {"name": "Derek", "service": "Mabel"}

        text_body, html_body = renderer.render_email_template("test_template", context)

        assert text_body is not None
        assert html_body is not None
        assert "Hello Derek!" in text_body
        assert "Welcome to Mabel" in text_body
        assert "<p>Hello Derek!</p>" in html_body
        assert "Welcome to Mabel" in html_body

    def test_render_text_only_template(self, temp_template_dir):
        """Test rendering template with only text variant."""
        renderer = EmailTemplateRenderer(temp_template_dir)
        context = {"message": "Test message"}

        text_body, html_body = renderer.render_email_template("text_only", context)

        assert text_body is not None
        assert "Text only: Test message" in text_body
        assert html_body is None

    def test_render_html_only_template(self, temp_template_dir):
        """Test rendering template with only HTML variant."""
        renderer = EmailTemplateRenderer(temp_template_dir)
        context = {"message": "Test message"}

        text_body, html_body = renderer.render_email_template("html_only", context)

        assert text_body is None
        assert html_body is not None
        assert "<p>HTML only: Test message</p>" in html_body

    def test_render_nonexistent_template_fails(self, temp_template_dir):
        """Test rendering nonexistent template raises error."""
        renderer = EmailTemplateRenderer(temp_template_dir)

        with pytest.raises(TemplateError) as exc_info:
            renderer.render_email_template("nonexistent", {})

        assert "not found" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_render_with_missing_variable(self, temp_template_dir):
        """Test rendering with missing variable renders as empty (Jinja2 default behavior)."""
        renderer = EmailTemplateRenderer(temp_template_dir)

        # Missing 'name' and 'service' in context - Jinja2 renders undefined vars as empty
        text_body, html_body = renderer.render_email_template("test_template", {})

        # Variables should be rendered as empty strings
        assert text_body is not None
        assert "Hello !" in text_body  # Empty name
        assert "Welcome to ." in text_body  # Empty service

    def test_template_exists(self, temp_template_dir):
        """Test template_exists method."""
        renderer = EmailTemplateRenderer(temp_template_dir)

        assert renderer.template_exists("test_template") is True
        assert renderer.template_exists("text_only") is True
        assert renderer.template_exists("html_only") is True
        assert renderer.template_exists("nonexistent") is False

    def test_auto_escape_enabled(self, temp_template_dir):
        """Test that auto-escaping is enabled for security."""
        renderer = EmailTemplateRenderer(temp_template_dir)

        # Create template with potentially dangerous content
        dangerous_template = temp_template_dir / "dangerous.html.j2"
        dangerous_template.write_text("<p>{{ user_input }}</p>")

        text_body, html_body = renderer.render_email_template(
            "dangerous",
            {"user_input": "<script>alert('xss')</script>"}
        )

        # Should be escaped
        assert html_body is not None
        assert "&lt;script&gt;" in html_body
        assert "<script>" not in html_body

    def test_render_with_complex_context(self, temp_template_dir):
        """Test rendering with complex nested context."""
        # Create template with nested variables
        complex_template = temp_template_dir / "complex.txt.j2"
        complex_template.write_text("User: {{ user.name }}\nItems: {% for item in items %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}")

        renderer = EmailTemplateRenderer(temp_template_dir)
        context = {
            "user": {"name": "Derek"},
            "items": ["apple", "banana", "cherry"]
        }

        text_body, html_body = renderer.render_email_template("complex", context)

        assert "User: Derek" in text_body
        assert "apple, banana, cherry" in text_body


class TestConvenienceFunctions:
    """Test convenience functions for template rendering."""

    def test_render_email_template_function(self, temp_template_dir):
        """Test the convenience render_email_template function."""
        # Note: This function uses a global singleton, so we need to be careful
        # For this test, we'll import and use it directly
        from services.templates import EmailTemplateRenderer, _renderer

        # Reset global renderer
        import services.templates
        services.templates._renderer = EmailTemplateRenderer(temp_template_dir)

        text_body, html_body = render_email_template(
            "test_template",
            {"name": "Test", "service": "Bot"}
        )

        assert text_body is not None
        assert "Hello Test!" in text_body
        assert html_body is not None


class TestActualTemplates:
    """Test the actual email templates in the project."""

    def test_example_welcome_template_exists(self):
        """Test that example_welcome template exists and renders."""
        # This tests the actual templates in templates/emails/
        from pathlib import Path
        template_dir = Path(__file__).parent.parent.parent / "templates" / "emails"

        if not template_dir.exists():
            pytest.skip("Template directory not found in expected location")

        renderer = EmailTemplateRenderer(template_dir)

        # Test that example_welcome exists
        assert renderer.template_exists("example_welcome")

        # Test rendering
        context = {"user_name": "Derek"}
        text_body, html_body = renderer.render_email_template("example_welcome", context)

        # Both variants should exist
        assert text_body is not None
        assert html_body is not None

        # Check content
        assert "Derek" in text_body
        assert "Derek" in html_body
        assert "Welcome" in text_body.lower() or "welcome" in text_body
