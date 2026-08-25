# AirGuard Community Dashboard Implementation Plan and Status

Status as of August 24, 2026: the non-forecast application and operational pipeline described below are implemented. Forecast generation/model development remains separate; the dashboard only consumes fresh, provenance-labeled `Forecast` rows. See `README.md` for deployment and activation instructions.

## 1. Purpose

Build a bilingual, responsive Django dashboard that helps community members understand current and predicted indoor PM2.5 conditions at participating buildings and decide what action to take.

The interface will emphasize design simplicity. Each page will answer one primary question, and features that do not directly support current readings, forecasts, education, notifications, accessibility, or data access will remain outside the first release.

Research references:

- [Love My Air Wisconsin](https://www.dhs.wisconsin.gov/climate/air.htm)
- [EPA Enhanced Air Sensor Guidebook](https://www.epa.gov/air-sensor-toolbox/how-use-air-sensors-air-sensor-guidebook)
- [EPA AQI Breakpoints](https://aqs.epa.gov/aqsweb/documents/codetables/aqi_breakpoints.html)

## 2. Audience

- Primary: community members seeking clear local indoor-air information.
- Secondary: authenticated staff signing up for building alerts through an unlisted, `noindex` URL.
- Facility managers will not receive a separate dashboard, sensor comparison tools, or operational controls.

## 3. Mockup Review Gate

Create a responsive, clickable prototype before beginning Django implementation. The prototype will contain:

1. Homepage with the citywide indoor-network median AQI, next-24-hour prediction, reporting coverage, update time, one action message, and three building links near the bottom.
2. Current Readings page with three building tiles, distinct icons, names, current median categories, and freshness indicators.
3. Building page with widgets for every enabled sensor in the authoritative manifest plus short educational guidance.
4. Sensor History dialog with current AQI and PM2.5, History and Forecast tabs, a time-range selector, accessible chart, equivalent table, and CSV download.
5. Sensor Forecast dialog with projected PM2.5/AQI, temperature, relative humidity, wind speed, wind direction, peak category, forecast time, and action guidance.
6. Public notification form.
7. Unlisted facility-manager notification form.
8. Additional Resources page and mobile versions of all core screens.

Implementation will begin only after the mockups are reviewed and approved.

## 4. Visual Direction

- Use a provisional AirGuard identity with neutral surfaces, charcoal text, sky-blue actions, green secondary accents, and a restrained yellow highlight.
- Reserve EPA AQI colors for air-quality status. Pair every color with a category label and other non-color cue.
- Use a system sans-serif font and restrained component styling with no oversized hero treatment.
- Use cards only for buildings, sensor widgets, and dialogs. Keep educational sections unframed.
- Use semantic HTML and a small custom CSS layer. Bootstrap is not required because the interface has a limited component set and avoiding it reduces styling overrides and dependency weight.
- Use familiar Lucide icons for navigation, locations, language, alerts, downloads, and dialog controls.

## 5. Pages and Behavior

### Homepage

- Show one clearly labeled "Indoor Air Across Participating Buildings" status.
- Calculate the current status as the median AQI of all valid sensors.
- Calculate the prediction as the highest hourly network-median AQI expected during the next 24 hours.
- Show the number of reporting sensors and the latest update time.
- Mark the aggregate unavailable when fewer than half of all sensors are current.
- Provide compact links to the three buildings near the bottom of the page.

### Current Readings

- List all participating buildings in a responsive grid.
- Show each building's name, icon, median AQI category, and update status.
- Open the corresponding building page when selected.
- Do not include a map, search, sorting, comparisons, or favorites in the first release.

### Building Page

- Show one widget for each enabled sensor configured for the building.
- Display AQI as the dominant value with PM2.5 in `micrograms/m3` beneath it.
- Include the category, observation timestamp, and freshness state.
- Open the sensor dialog when a widget is selected.
- Follow the widgets with concise "What this means" and "What you can do" sections.

### Sensor Dialog

- Use an accessible native dialog with History and Forecast tabs.
- Default History to 24 hours with options for 7 days and 30 days.
- Provide a line chart, keyboard-readable point information, and an equivalent data table.
- Provide a CSV download matching the selected sensor and time range.
- Show the forecast as 24 hourly PM2.5/AQI points with compact supporting weather information.
- Keep PM2.5 dominant; weather must remain secondary supporting context.

### Notifications

- Public route: `/notifications/`.
- Facility route: `/facility-notifications/`, staff-authenticated and excluded from navigation and search indexing.
- Collect email, building, AQI/WHO/EPA alert rule, language, audience, and explicit consent.
- Verify the address before activation and provide a signed unsubscribe link.
- Evaluate fresh forecasts and send idempotent alert email through a retrying database outbox.
- Resubmitting an existing email, building, and audience combination updates the stored preference.

### Additional Resources

- Provide a short curated list of EPA, AirNow, Love My Air, PM2.5, AQI, and health-action resources.
- Link to Spanish resources when authoritative translated versions are available.

## 6. Technical Architecture

- Use Python 3.12 or newer through the project `.venv`.
- Use Django 5.2 LTS with Django templates, SQLite, plain CSS, and minimal vanilla JavaScript.
- Serve pages and replaceable mock JSON endpoints from one Django process at `127.0.0.1:8000`.
- Use English server-rendered content with an English/Spanish client-side language control.
- Poll current data every 60 seconds; do not use WebSockets.
- Mark a sensor unavailable when its newest sample is more than 15 minutes old.
- Calculate PM2.5 AQI with EPA NowCast and current EPA breakpoints.
- Clearly label the result as guidance from indoor low-cost sensors rather than regulatory ambient monitoring.

Minimal data models:

- Building: slug, name, icon, display order.
- Sensor: building, public name, placement, external identifier, source, enabled state, time zone, calibration, and display order.
- Reading: sensor, observation time, PM2.5, and optional ingest-batch provenance.
- Forecast: sensor, forecast time, PM2.5, weather fields, generation time, source, and run ID.
- Subscription: email, building, threshold kind/value, locale, audience, consent/verification state, alert state, and timestamps.
- InboundMessage/IngestBatch: immutable raw evidence, deduplication hashes, results, and errors.
- AlertEvent/OutboundEmail/Suppression/ProviderEvent: idempotent evaluation, delivery/retry state, and provider feedback.

## 7. API Interfaces

- `GET /api/v1/status/`
- `GET /api/v1/buildings/`
- `GET /api/v1/buildings/<slug>/`
- `GET /api/v1/sensors/<id>/readings/?range=24h|7d|30d`
- `GET /api/v1/sensors/<id>/readings.csv?range=24h|7d|30d`
- `GET /api/v1/sensors/<id>/forecast/`
- `POST /api/v1/subscriptions/`
- `POST /api/v1/measurements/govee/`
- `POST /api/v1/measurements/custom/`
- `POST /api/v1/email-events/postmark/`
- `GET /health/`

Use timezone-aware ISO 8601 timestamps. Reading responses expose PM2.5, AQI, category, observation time, and data-quality state. Forecast responses additionally expose temperature, relative humidity, wind speed, and wind direction.

Limit chart responses to 168 points: hourly values for 24 hours and 7 days, and six-hour aggregates for 30 days. CSV downloads include timestamp, PM2.5, AQI, category, and data-quality status.

## 8. Development Data

- Seed Riverside Community Center, Eastview School, and Northside Library.
- Create gym, hallway, and entrance sensors for each building.
- Generate 30 days of five-minute readings and 24 hours of hourly forecasts.
- Include normal, elevated, forecast-warning, missing-history, and stale-sensor examples.
- Generate weather values that remain internally plausible but are clearly test data.

## 9. Accessibility Requirements

WCAG 2.2 Level AA conformance is an acceptance requirement.

- Use semantic landmarks, ordered heading levels, descriptive page titles, and a skip link.
- Ensure complete keyboard access and visible focus indicators.
- Maintain focus correctly when dialogs open and close; support Escape to close.
- Associate every form field with a visible label and connect validation messages programmatically.
- Use status text and icons in addition to color.
- Meet AA contrast requirements for text, controls, focus states, charts, and AQI categories.
- Support text zoom to 200 percent and reflow at 320 CSS pixels without horizontal page scrolling.
- Use touch targets of at least 24 by 24 CSS pixels, with larger targets for primary actions.
- Respect `prefers-reduced-motion` and avoid essential animation.
- Provide chart summaries and equivalent data tables for nonvisual access.
- Announce refreshed status data without unexpectedly moving focus.
- Translate accessible names, validation, status messages, chart summaries, and educational content into Spanish.
- Include accessible loading, empty, error, stale, and unavailable states.

## 10. Libraries

Required:

- `Django==5.2.16`
- `waitress==3.0.2`
- `whitenoise==6.12.0`
- Minimal native SVG charts and text/icon treatments; no browser package runtime is required.

Included without separate installation:

- SQLite
- Django forms and validation
- Django `JsonResponse` and streaming CSV responses
- Django internationalization
- Django test runner

Do not add Django REST Framework, CORS middleware, Bootstrap, Tailwind, jQuery, a frontend framework, an email library, or a background worker unless later requirements establish a concrete need.

## 11. Verification

- Test EPA breakpoints, NowCast weighting, insufficient history, median aggregation, forecast peaks, stale exclusion, and unavailable aggregate behavior.
- Test API success and error responses, every history range, CSV contents and headers, unknown resources, invalid subscriptions, and preference updates.
- Test current readings, building navigation, dialogs, tabs, range changes, data-table equivalence, downloads, language switching, and both notification routes.
- Run automated accessibility checks on every page and dialog state.
- Perform keyboard-only and screen-reader-oriented manual reviews in English and Spanish.
- Verify responsive layouts at 320, 768, and 1440 CSS pixels and at 200 percent text zoom.
- Confirm weather information is secondary, readable, correctly labeled with units, and available without interpreting a chart.

## 12. Remaining Outside the Implemented Scope

- Forecast model/generation and live external weather integration
- General public user accounts or a separate facility dashboard
- Sensor comparison tools
- Maps, search, sorting, and favorites
- Product analytics and custom administrative reporting beyond Django admin/health data
- Multi-host production database migration
- External DNS/TLS, email-provider verification, backup-service configuration, and Task Scheduler activation
