import pytest
from addok.shell import Cmd


class TestShellFilterParsing:
    """Tests for shell filter parsing (_parse_filters method)."""

    @pytest.fixture(scope="class")
    def cmd(self):
        """Create a single Cmd instance for all tests in this class."""
        from addok.config import config
        config.FILTERS = ["type", "postcode"]
        return Cmd()

    def test_parse_single_filter(self, cmd):
        """Test parsing a single filter value."""
        query = "rue des lilas TYPE street LIMIT 10"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": "street"}
        assert "TYPE" not in remaining
        assert "rue des lilas" in remaining
        assert "LIMIT 10" in remaining

    def test_parse_filters_with_coordinates(self, cmd):
        """Test parsing filters when coordinates are present (REVERSE use case)."""
        query = "48.1234 2.9876 TYPE street LIMIT 5"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": "street"}
        assert "TYPE" not in remaining
        assert "48.1234 2.9876" in remaining
        assert "LIMIT 5" in remaining

    def test_parse_repeated_filters(self, cmd):
        """Test parsing repeated filter parameters (TYPE street TYPE city)."""
        query = "rue des lilas TYPE street TYPE city"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": ["street", "city"]}
        assert "TYPE" not in remaining
        assert "rue des lilas" in remaining

    def test_parse_filter_with_separator(self, cmd):
        """Test parsing filter with pipe separator (TYPE street|city)."""
        query = "rue des lilas TYPE street|city"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": ["street", "city"]}
        assert "TYPE" not in remaining
        assert "rue des lilas" in remaining

    def test_parse_filter_with_three_values(self, cmd):
        """Test parsing filter with three values via separator."""
        query = "paris TYPE street|city|locality"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": ["street", "city", "locality"]}
        assert "TYPE" not in remaining
        assert "paris" in remaining

    def test_parse_mixed_repetition_and_separator(self, cmd):
        """Test combining repetition and separator (TYPE street|city TYPE locality)."""
        query = "paris TYPE street|city TYPE locality"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": ["street", "city", "locality"]}
        assert "TYPE" not in remaining

    def test_parse_multiple_different_filters(self, cmd):
        """Test parsing different filter types."""
        query = "rue TYPE street POSTCODE 75000"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": "street", "postcode": "75000"}
        assert "TYPE" not in remaining
        assert "POSTCODE" not in remaining
        assert "rue" in remaining

    def test_parse_multiple_filters_with_multi_values(self, cmd):
        """Test multiple filters with multi-values each."""
        query = "paris TYPE street TYPE city POSTCODE 75000 POSTCODE 77000"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {
            "type": ["street", "city"],
            "postcode": ["75000", "77000"]
        }
        assert "paris" in remaining

    def test_parse_no_filters(self, cmd):
        """Test query without filters."""
        query = "rue des lilas LIMIT 10"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {}
        assert remaining == query

    def test_parse_filter_with_equals_sign(self, cmd):
        """Test filter with = separator (TYPE=street)."""
        query = "rue TYPE=street"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": "street"}
        assert "TYPE" not in remaining

    def test_parse_filter_with_whitespace(self, cmd):
        """Test filter values are stripped of whitespace."""
        query = "rue TYPE street|city"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": ["street", "city"]}
        # No trailing spaces in values

    def test_parse_empty_separator_values_ignored(self, cmd):
        """Test empty values from separator are ignored (TYPE street||city)."""
        query = "rue TYPE street||city"
        remaining, filters = cmd._parse_filters(query)

        assert filters == {"type": ["street", "city"]}

    def test_backward_compatibility_single_value_as_string(self, cmd):
        """Test single value is returned as string, not list (backward compat)."""
        query = "rue TYPE street"
        remaining, filters = cmd._parse_filters(query)

        # Single value should be string, not list
        assert isinstance(filters["type"], str)
        assert filters["type"] == "street"

    def test_multi_value_as_list(self, cmd):
        """Test multiple values are returned as list."""
        query = "rue TYPE street TYPE city"
        remaining, filters = cmd._parse_filters(query)

        # Multiple values should be list
        assert isinstance(filters["type"], list)
        assert filters["type"] == ["street", "city"]
