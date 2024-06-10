{% macro slugify_column_values(string) %}
    regexp_replace(
        regexp_replace(
            regexp_replace(
                regexp_replace(lower({{ string }}), '[ -]+', '_'),
                '^[0-9]',
                concat('_', substr({{ string }}, 1, 1))
            ),
            '[^a-z0-9_]+',
            ''
        ),
        '[ .]+',
        '_'
    )
{% endmacro %}
