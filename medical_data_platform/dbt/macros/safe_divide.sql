{% macro safe_divide(numerator, denominator) %}
    case when {{ denominator }} = 0 or {{ denominator }} is null
         then null
         else {{ numerator }}::numeric / {{ denominator }}
    end
{% endmacro %}
