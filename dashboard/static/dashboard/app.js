(() => {
  const translations = {
    es: {
      skip: "Saltar al contenido principal", tagline: "El aire comunitario, más claro", language: "Idioma",
      home: "Inicio", readings: "Lecturas actuales", resources: "Recursos", signup: "Inscribirse",
      sensorFooter: "Datos de sensores interiores de bajo costo para orientación comunitaria.",
      communityStatus: "Aire interior en edificios participantes", statusIntro: "Una vista sencilla de las condiciones reportadas por los sensores AirGuard en espacios comunitarios.",
      updated: "Actualizado", ago: "atrás", current: "Actual:", of: "de", reporting: "sensores reportando", forecast: "Pronóstico:",
      statusMessage: "La mayoría de las personas pueden continuar sus actividades normales. Las personas sensibles a la contaminación por partículas pueden reducir el esfuerzo.",
      chooseBuilding: "Elija un edificio", buildingIntro: "Vea las lecturas del gimnasio, pasillo y entrada.", allBuildings: "Todos los edificios", sensors: "sensores",
      gym: "Gimnasio", hallway: "Pasillo", entrance: "Entrada", unavailable: "No disponible", unhealthy: "Insalubre", "very-unhealthy": "Muy insalubre", hazardous: "Peligroso",
      currentReadingsTitle: "Lecturas actuales", readingsIntro: "Seleccione un edificio participante para ver sus sensores interiores.", clickBuilding: "Seleccione cualquier tarjeta de edificio para ver las lecturas de su gimnasio, pasillo y entrada.",
      backBuildings: "Volver a edificios", buildingDetailIntro: "Lecturas interiores de PM2.5 de tres espacios compartidos.",
      whatMeans: "Qué significa", meansText: "PM2.5 está compuesto por partículas diminutas que pueden penetrar profundamente en los pulmones. El AQI convierte la lectura en una categoría de salud más fácil de entender.",
      learnMore: "Más información", whatDo: "Qué puede hacer", actionOne: "Elija una sala con una lectura más baja cuando sea posible.", actionTwo: "Las personas con asma o afecciones cardíacas deben seguir su plan de atención.", actionThree: "Revise nuevamente antes de realizar actividad intensa.",
      resourcesTitle: "Recursos sobre la calidad del aire", resourcesIntro: "Actividades, cuentos, orientación de salud y herramientas prácticas para familias, estudiantes y grupos comunitarios.",
      learnTeach: "Aprender y enseñar", familiesKids: "Para familias y niños", communityAction: "Acción comunitaria", healthGuidance: "Salud y orientación sobre el AQI", sensorLimits: "Acerca de estos sensores:",
      sensorLimitsText: "AirGuard utiliza sensores interiores de bajo costo como orientación comunitaria. Estas lecturas no son mediciones reglamentarias del aire ambiente.",
      signupTitle: "Reciba notificaciones sobre la calidad del aire", signupIntro: "Elija un edificio y el nivel de AQI para recibir una notificación.", facilityEyebrow: "Acceso para administradores de instalaciones", facilityTitle: "Notificaciones de alertas del edificio", facilityIntro: "Este formulario no listado guarda preferencias de notificación a nivel del edificio.",
      email: "Correo electrónico", building: "Edificio", notifyAt: "Notificarme en", consent: "Acepto recibir notificaciones por correo electrónico de AirGuard. El envío se añadirá en una fase posterior.", savePreference: "Guardar preferencia", saved: "Su preferencia de notificación se guardó.",
      whatAqi: "¿Qué significa AQI?", aqiExplanation: "El AQI convierte una medición de PM2.5 en una categoría de salud. Un número más alto significa más contaminación por partículas y una mayor posibilidad de efectos en la salud.",
      good: "Bueno", moderate: "Moderado", sensitive: "Insalubre para grupos sensibles", goodGuidance: "La calidad del aire es satisfactoria para la mayoría de las personas.", moderateGuidance: "Las personas inusualmente sensibles a la contaminación por partículas pueden notar efectos.", sensitiveGuidance: "Los niños y las personas con afecciones cardíacas o pulmonares deben reducir el esfuerzo prolongado.", indoorNote: "AirGuard aplica categorías de salud del AQI a lecturas de sensores interiores de bajo costo como orientación comunitaria. No es un informe reglamentario del AQI exterior.", close: "Cerrar",
      history: "Historial", pmHistory: "Historial de PM2.5", timeRange: "Intervalo", viewTable: "Ver tabla de datos", time: "Hora", category: "Categoría", downloadCsv: "Descargar CSV", forecastAction: "Las personas sensibles a la contaminación por partículas deberían considerar una sala con una lectura más baja durante la tarde.", next24: "Próximas 24 horas"
    }
  };

  const languageSelect = document.querySelector("#language-select");
  const localeInput = document.querySelector("#id_locale");

  function applyLanguage(language) {
    document.documentElement.lang = language;
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.dataset.english ||= element.textContent;
      element.textContent = language === "es" && translations.es[element.dataset.i18n] || element.dataset.english;
    });
    if (languageSelect) languageSelect.value = language;
    if (localeInput) localeInput.value = language;
    document.querySelectorAll("#id_threshold option").forEach((option) => {
      option.dataset.english ||= option.textContent;
      const spanish = { "51": "Moderado o superior", "101": "Insalubre para grupos sensibles o superior", "151": "Insalubre o superior" };
      option.textContent = language === "es" && spanish[option.value] || option.dataset.english;
    });
    localStorage.setItem("airguard-language", language);
  }

  if (languageSelect) languageSelect.addEventListener("change", (event) => applyLanguage(event.target.value));
  applyLanguage(localStorage.getItem("airguard-language") || "en");

  const aqiDialog = document.querySelector("#aqi-dialog");
  document.querySelector("[data-open-aqi]")?.addEventListener("click", () => aqiDialog.showModal());
  document.querySelectorAll("[data-close-aqi]").forEach((button) => button.addEventListener("click", () => aqiDialog.close()));

  const sensorDialog = document.querySelector("#sensor-dialog");
  if (!sensorDialog) return;

  const rangeSelect = document.querySelector("#history-range");
  const downloadLink = document.querySelector("#download-link");
  let selectedSensor = null;
  let forecastLoaded = false;

  function localizedCategory(category) {
    if (document.documentElement.lang !== "es") return category;
    return { "Good": "Bueno", "Moderate": "Moderado", "Unhealthy for sensitive groups": "Insalubre para grupos sensibles", "Unhealthy": "Insalubre", "Very unhealthy": "Muy insalubre", "Hazardous": "Peligroso" }[category] || category;
  }

  function drawChart(svg, values, labels) {
    const width = 760, height = 280, left = 50, right = 18, top = 18, bottom = 40;
    const maximum = Math.max(45, ...values, 1);
    const x = (index) => left + index / Math.max(values.length - 1, 1) * (width - left - right);
    const y = (value) => top + (1 - value / maximum) * (height - top - bottom);
    const ticks = [0, 10, 20, 30, 40].filter((tick) => tick <= maximum);
    let markup = ticks.map((tick) => `<line class="chart-grid" x1="${left}" y1="${y(tick)}" x2="${width-right}" y2="${y(tick)}"></line><text class="chart-axis" x="8" y="${y(tick)+4}">${tick}</text>`).join("");
    if (values.length) {
      markup += `<path class="chart-line" d="${values.map((value, index) => `${index ? "L" : "M"} ${x(index).toFixed(1)} ${y(value).toFixed(1)}`).join(" ")}"></path>`;
      const interval = Math.max(1, Math.floor(values.length / 8));
      values.forEach((value, index) => {
        if (index % interval === 0 || index === values.length - 1) markup += `<circle class="chart-point" cx="${x(index)}" cy="${y(value)}" r="4"><title>${labels[index]}: ${value.toFixed(1)} µg/m³</title></circle>`;
      });
      markup += `<text class="chart-axis" x="${left}" y="${height-8}">${labels[0]}</text><text class="chart-axis" text-anchor="end" x="${width-right}" y="${height-8}">${labels.at(-1)}</text>`;
    }
    [...svg.querySelectorAll("line, path, circle, text")].forEach((node) => node.remove());
    svg.insertAdjacentHTML("beforeend", markup);
  }

  async function loadHistory() {
    const response = await fetch(`/api/v1/sensors/${selectedSensor}/readings/?range=${rangeSelect.value}`);
    const data = await response.json();
    const readings = data.readings;
    const values = readings.map((item) => item.pm25);
    const labels = readings.map((item) => new Date(item.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "numeric" }));
    drawChart(document.querySelector("#history-chart"), values, labels);
    document.querySelector("#history-summary").textContent = readings.length ? `PM2.5 ranged from ${Math.min(...values).toFixed(1)} to ${Math.max(...values).toFixed(1)} µg/m³.` : "No readings are available for this range.";
    document.querySelector("#history-table").innerHTML = readings.slice(-24).map((item) => `<tr><td>${new Date(item.timestamp).toLocaleString()}</td><td>${item.pm25.toFixed(1)} µg/m³</td><td>${item.aqi}</td><td>${localizedCategory(item.category)}</td></tr>`).join("");
    downloadLink.href = `/api/v1/sensors/${selectedSensor}/readings.csv?range=${rangeSelect.value}`;
  }

  async function loadForecast() {
    if (forecastLoaded) return;
    const response = await fetch(`/api/v1/sensors/${selectedSensor}/forecast/`);
    const data = await response.json();
    const forecasts = data.forecasts;
    const peak = forecasts.reduce((best, item) => !best || item.aqi > best.aqi ? item : best, null);
    document.querySelector("#forecast-peak").textContent = peak ? `${document.documentElement.lang === "es" ? "Pronóstico máximo" : "Peak forecast"}: ${localizedCategory(peak.category)} ${document.documentElement.lang === "es" ? "a las" : "at"} ${new Date(peak.timestamp).toLocaleTimeString([], { hour: "numeric" })}` : "Forecast unavailable";
    const first = forecasts[0];
    document.querySelector("#weather-grid").innerHTML = first ? [
      ["Temperature", `${Math.round(first.temperature)} °F`], ["Relative humidity", `${first.relative_humidity}%`],
      ["Wind speed", `${first.wind_speed.toFixed(1)} mph`], ["Wind direction", first.wind_direction]
    ].map(([label, value]) => `<div class="weather-item"><small>${label}</small><strong>${value}</strong></div>`).join("") : "";
    drawChart(document.querySelector("#forecast-chart"), forecasts.map((item) => item.pm25), forecasts.map((item) => new Date(item.timestamp).toLocaleTimeString([], { hour: "numeric" })));
    forecastLoaded = true;
  }

  document.querySelectorAll("[data-sensor-id]").forEach((button) => button.addEventListener("click", async () => {
    selectedSensor = button.dataset.sensorId;
    forecastLoaded = false;
    document.querySelector("#sensor-dialog-title").textContent = button.dataset.sensorName;
    document.querySelector("#dialog-building").textContent = button.dataset.buildingName;
    document.querySelector("#dialog-current").textContent = button.querySelector(".sensor-status").textContent.trim();
    sensorDialog.showModal();
    await loadHistory();
  }));
  document.querySelector("[data-close-sensor]").addEventListener("click", () => sensorDialog.close());
  rangeSelect.addEventListener("change", loadHistory);
  document.querySelectorAll("[data-tab]").forEach((tab) => tab.addEventListener("click", async () => {
    document.querySelectorAll("[data-tab]").forEach((item) => item.setAttribute("aria-selected", item === tab ? "true" : "false"));
    document.querySelectorAll(".dialog-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `${tab.dataset.tab}-panel`));
    if (tab.dataset.tab === "forecast") await loadForecast();
  }));
})();
