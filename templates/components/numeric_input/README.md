# Components

## `numeric_input/main.html`

Reusable Django template component for grouped-number inputs.

### Purpose

Use this component when a form field should:

- display numbers with comma grouping
- optionally show `Clear`, `+`, and `-` controls
- support a configurable increment step

### Include examples

Basic integer input with side controls:

```django
{% include "components/numeric_input/main.html" with field=form.quantity show_spinner_controls=True %}
```

Money input with a larger step:

```django
{% include "components/numeric_input/main.html" with field=form.price show_spinner_controls=True step_value=1000 %}
```

Grouped-number input without side controls:

```django
{% include "components/numeric_input/main.html" with field=form.some_number %}
```

### Full form example

Example: use the component inside a Django form page.

```django
<form method="post" novalidate>
    {% csrf_token %}

    <div class="row g-3">
        <div class="col-12 col-lg-6">
            {% include "components/numeric_input/main.html" with field=form.quantity show_spinner_controls=True %}
        </div>

        <div class="col-12 col-lg-6">
            {% include "components/numeric_input/main.html" with field=form.price show_spinner_controls=True step_value=1000 %}
        </div>
    </div>

    <button type="submit" class="btn btn-primary">Save</button>
</form>
```

In this example:

- `quantity` increases and decreases by `1`
- `price` increases and decreases by `1000`
- the actual `<input>` still uses the Django field id, name, and value under the hood

### How another script gets the value

The component does not create a custom data model. The real source of truth is still the input element rendered by Django.

Example:

```html+django
{% include "components/numeric_input/main.html" with field=form.price show_spinner_controls=True step_value=1000 %}

<script>
    const priceInput = document.getElementById('{{ form.price.id_for_label }}');

    const parseGroupedNumber = (value) => {
        const normalized = String(value || '').replace(/,/g, '').replace(/[^\d]/g, '').trim();
        return normalized ? Number.parseInt(normalized, 10) : 0;
    };

    const rawValue = parseGroupedNumber(priceInput.value);
    console.log(rawValue); // 1500000
</script>
```

Notes:

- Do not read the displayed value directly if you need a pure number, because the input may contain commas such as `1,500,000`.
- In JavaScript, remove commas before converting to `Number` or `parseInt`.

### How another script sets the value

If another component or script wants to update the numeric input, set the input value and then trigger the `input` event so dependent logic can react.

Example:

```html+django
{% include "components/numeric_input/main.html" with field=form.price show_spinner_controls=True step_value=1000 %}

<script>
    const priceInput = document.getElementById('{{ form.price.id_for_label }}');

    const formatGroupedNumber = (value) => new Intl.NumberFormat('en-US', {
        maximumFractionDigits: 0,
    }).format(Math.max(0, Math.trunc(value)));

    const setNumericInputValue = (input, nextValue) => {
        input.value = formatGroupedNumber(nextValue);
        input.dispatchEvent(new Event('input', { bubbles: true }));
    };

    setNumericInputValue(priceInput, 2500000);
</script>
```

Notes:

- Prefer setting a formatted string such as `2,500,000`, not a raw unformatted value, so the UI remains consistent immediately.
- Triggering `input` is important when other scripts are listening for live recalculation.
- If the field is disabled, external scripts should treat it as read-only.

### Parameters

- `field`
  - Required.
  - Must be a bound Django form field.

- `show_spinner_controls`
  - Optional.
  - When `True`, renders `Clear`, `+`, and `-`.
  - When omitted or falsey, only the input is shown.

- `step_value`
  - Optional.
  - Default is `1`.
  - Use `1000` for money fields in this project.

### Behavior notes

- If the field is disabled, the side controls are hidden automatically.
- The component includes its own CSS and JS, so pages can reuse it directly without extra setup.
- The input assumes grouped-number formatting is already enabled by the Django form field/widget pipeline used in this project.
- Other scripts should interact with the underlying input element by `id` or `name`, not by trying to control the `Clear`, `+`, and `-` buttons directly.
