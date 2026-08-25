(() => {
  const translations = {
    es: {
      skip: "Saltar al contenido principal", tagline: "El aire comunitario, más claro", language: "Idioma", airguardHome: "Inicio de AirGuard", primaryNav: "Navegación principal", closeAqi: "Cerrar información del AQI", aqiExamples: "Ejemplos de categorías del AQI", closeSensor: "Cerrar detalles del sensor", sensorDetails: "Detalles del sensor",
      home: "Inicio", readings: "Lecturas actuales", resources: "Recursos", signup: "Inscribirse",
      sensorFooter: "Datos de sensores interiores de bajo costo para orientación comunitaria.", footerDescription: "Información práctica sobre el aire interior para edificios comunitarios participantes.", explore: "Explorar", learn: "Aprender",
      communityStatus: "Aire interior en edificios participantes", statusIntro: "Una vista sencilla de las condiciones reportadas por los sensores AirGuard en espacios comunitarios.",
      updated: "Actualizado", ago: "atrás", current: "Actual:", of: "de", reporting: "sensores reportando", forecast: "Pronóstico:",
      unavailableMessage: "Datos no disponibles. Vuelva a revisar después de que los sensores participantes envíen mediciones actuales.", goodStatusMessage: "Las condiciones de calidad del aire son favorables para la mayoría de las personas.", moderateStatusMessage: "La mayoría de las personas puede continuar sus actividades normales. Las personas sensibles quizá prefieran una sala con una lectura menor.", unhealthyStatusMessage: "Los niveles de partículas pueden afectar la salud. Considere una sala con una lectura menor y reduzca la actividad intensa.",
      chooseBuilding: "Resumen de edificios", buildingIntro: "Vea las lecturas de los espacios comunitarios monitoreados.", allBuildings: "Todos los edificios", sensors: "sensores",
      gym: "Gimnasio", hallway: "Pasillo", entrance: "Entrada", unavailable: "No disponible", unhealthy: "Insalubre", "very-unhealthy": "Muy insalubre", hazardous: "Peligroso",
      currentReadingsTitle: "Lecturas actuales", readingsIntro: "Seleccione un edificio participante para ver sus sensores interiores.", clickBuilding: "Seleccione cualquier tarjeta de edificio para explorar las lecturas de sus espacios monitoreados.",
      backBuildings: "Volver a edificios", buildingDetailIntro: "Lecturas interiores de PM2.5 de espacios compartidos monitoreados.", lastReading: "Última lectura",
      whatMeans: "Qué significa", meansText: "PM2.5 está compuesto por partículas diminutas que pueden penetrar profundamente en los pulmones. El AQI convierte la lectura en una categoría de salud más fácil de entender.",
      learnMore: "Más información", whatDo: "Qué puede hacer", actionOne: "Elija una sala con una lectura más baja cuando sea posible.", actionTwo: "Las personas con asma o afecciones cardíacas deben seguir su plan de atención.", actionThree: "Revise nuevamente antes de realizar actividad intensa.",
      resourcesTitle: "Recursos sobre la calidad del aire", resourcesIntro: "Actividades, cuentos, orientación de salud y herramientas prácticas para familias, estudiantes y grupos comunitarios.",
      learnTeach: "Aprender y enseñar", familiesKids: "Para familias y niños", communityAction: "Acción comunitaria", healthGuidance: "Salud y orientación sobre el AQI", sensorLimits: "Acerca de estos sensores:",
      sensorLimitsText: "AirGuard utiliza sensores interiores de bajo costo como orientación comunitaria. Estas lecturas no son mediciones reglamentarias del aire ambiente.",
      signupTitle: "Reciba alertas previstas sobre la calidad del aire", signupIntro: "Elija un edificio y un umbral. Le enviaremos un correo cuando el pronóstico disponible indique que podría superarse.", facilityEyebrow: "Acceso para administradores de instalaciones", facilityTitle: "Alertas previstas del edificio", facilityIntro: "Configure alertas previstas verificadas para el edificio.",
      email: "Correo electrónico", building: "Edificio", notifyAt: "Notificarme en", consent: "Acepto recibir correos de AirGuard y entiendo que puedo cancelar en cualquier momento.", savePreference: "Guardar preferencia", saved: "Su preferencia activa se actualizó.", verificationQueued: "Revise su correo para confirmar y activar esta alerta.", benchmarkNote: "Las opciones de EPA y OMS usan promedios móviles de PM2.5 de 24 horas como referencias de salud interior; no son determinaciones regulatorias.",
      whatAqi: "¿Qué significa AQI?", aqiExplanation: "El AQI convierte una medición de PM2.5 en una categoría de salud. Un número más alto significa más contaminación por partículas y una mayor posibilidad de efectos en la salud.",
      good: "Bueno", moderate: "Moderado", sensitive: "Insalubre para grupos sensibles", goodGuidance: "La calidad del aire es satisfactoria para la mayoría de las personas.", moderateGuidance: "Las personas inusualmente sensibles a la contaminación por partículas pueden notar efectos.", sensitiveGuidance: "Los niños y las personas con afecciones cardíacas o pulmonares deben reducir el esfuerzo prolongado.", indoorNote: "AirGuard aplica categorías de salud del AQI a lecturas de sensores interiores de bajo costo como orientación comunitaria. No es un informe reglamentario del AQI exterior.", close: "Cerrar",
      history: "Historial", pmHistory: "Historial de PM2.5", historyChartTitle: "Gráfico histórico de PM2.5", forecastChartTitle: "Gráfico del pronóstico de PM2.5", timeRange: "Intervalo", viewTable: "Ver tabla de datos", viewForecastTable: "Ver tabla del pronóstico", time: "Hora", category: "Categoría", downloadCsv: "Descargar CSV", forecastAction: "Las personas sensibles a la contaminación por partículas deberían considerar una sala con una lectura más baja mientras se pronostiquen condiciones elevadas.", next24: "Próximas 24 horas",
      verifiedTitle: "Correo confirmado", verifiedText: "Su alerta prevista de AirGuard está activa.", unsubscribedTitle: "Alertas detenidas", unsubscribedText: "Esta dirección ya no recibirá alertas de AirGuard.", unsubscribeTitle: "¿Detener las alertas de AirGuard?", unsubscribeText: "Confirme que desea detener todas las alertas de esta suscripción.", confirmUnsubscribe: "Detener alertas", returnHome: "Volver a AirGuard"
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
    document.querySelectorAll("[data-i18n-label]").forEach((element) => {
      element.dataset.englishLabel ||= element.getAttribute("aria-label");
      element.setAttribute("aria-label", language === "es" && translations.es[element.dataset.i18nLabel] || element.dataset.englishLabel);
    });
    document.querySelectorAll("[data-relative-time]").forEach((element) => {
      const seconds = Math.max(0, (Date.now() - new Date(element.dateTime)) / 1000);
      const [unit, size] = seconds < 3600 ? ["minute", 60] : seconds < 86400 ? ["hour", 3600] : seconds < 2592000 ? ["day", 86400] : ["month", 2592000];
      element.textContent = new Intl.RelativeTimeFormat(language, {numeric: "always"}).format(-Math.round(seconds / size), unit);
    });
    if (languageSelect) languageSelect.value = language;
    if (localeInput) localeInput.value = language;
    document.querySelectorAll("#id_alert_rule option").forEach((option) => {
      option.dataset.english ||= option.textContent;
      const spanish = { aqi_51: "AQI previsto: moderado o superior", aqi_101: "AQI previsto: insalubre para grupos sensibles o superior", aqi_151: "AQI previsto: insalubre o superior", who_pm25_24h: "Guía OMS de PM2.5 de 24 horas (15 µg/m³)", epa_pm25_24h: "Estándar EPA de PM2.5 de 24 horas (35 µg/m³)" };
      option.textContent = language === "es" && spanish[option.value] || option.dataset.english;
    });
    document.querySelectorAll("#history-range option").forEach((option) => {
      option.dataset.english ||= option.textContent;
      const spanish = {"24h": "24 horas", "7d": "7 días", "30d": "30 días"};
      option.textContent = language === "es" ? spanish[option.value] : option.dataset.english;
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
    const summary = document.querySelector("#history-summary");
    try {
      const response = await fetch(`/api/v1/sensors/${selectedSensor}/readings/?range=${rangeSelect.value}`);
      if (!response.ok) throw new Error();
      const readings = (await response.json()).readings;
      const values = readings.map((item) => item.pm25);
      const labels = readings.map((item) => new Date(item.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "numeric" }));
      drawChart(document.querySelector("#history-chart"), values, labels);
      const spanish = document.documentElement.lang === "es";
      summary.textContent = readings.length ? `PM2.5 ${spanish ? "varió de" : "ranged from"} ${Math.min(...values).toFixed(1)} ${spanish ? "a" : "to"} ${Math.max(...values).toFixed(1)} µg/m³.` : (spanish ? "No hay lecturas para este intervalo." : "No readings are available for this range.");
      document.querySelector("#history-chart-desc").textContent = summary.textContent;
      document.querySelector("#history-table").innerHTML = readings.map((item) => `<tr><td>${new Date(item.timestamp).toLocaleString()}</td><td>${item.pm25.toFixed(1)} µg/m³</td><td>${item.aqi}</td><td>${localizedCategory(item.category)}</td></tr>`).join("");
      downloadLink.href = `/api/v1/sensors/${selectedSensor}/readings.csv?range=${rangeSelect.value}`;
    } catch (_) {
      summary.textContent = document.documentElement.lang === "es" ? "No se pudieron cargar las lecturas." : "Readings could not be loaded.";
    }
  }

  async function loadForecast() {
    if (forecastLoaded) return;
    const peakElement = document.querySelector("#forecast-peak");
    try {
      const response = await fetch(`/api/v1/sensors/${selectedSensor}/forecast/`);
      if (!response.ok) throw new Error();
      const forecasts = (await response.json()).forecasts;
      const peak = forecasts.reduce((best, item) => !best || item.aqi > best.aqi ? item : best, null);
      const spanish = document.documentElement.lang === "es";
      peakElement.textContent = peak ? `${spanish ? "Pronóstico máximo" : "Peak forecast"}: ${localizedCategory(peak.category)} ${spanish ? "a las" : "at"} ${new Date(peak.timestamp).toLocaleTimeString([], { hour: "numeric" })}` : (spanish ? "Pronóstico no disponible" : "Forecast unavailable");
      document.querySelector("#forecast-callout").hidden = false;
      document.querySelector("#forecast-action").hidden = !peak;
      const first = forecasts[0];
      const weather = spanish ? [
        ["Temperatura", first && `${Math.round(first.temperature)} °F`], ["Humedad relativa", first && `${first.relative_humidity}%`], ["Velocidad del viento", first && `${first.wind_speed.toFixed(1)} mph`], ["Dirección del viento", first && first.wind_direction]
      ] : [
        ["Temperature", first && `${Math.round(first.temperature)} °F`], ["Relative humidity", first && `${first.relative_humidity}%`], ["Wind speed", first && `${first.wind_speed.toFixed(1)} mph`], ["Wind direction", first && first.wind_direction]
      ];
      document.querySelector("#weather-grid").innerHTML = first ? weather.map(([label, value]) => `<div class="weather-item"><small>${label}</small><strong>${value}</strong></div>`).join("") : "";
      drawChart(document.querySelector("#forecast-chart"), forecasts.map((item) => item.pm25), forecasts.map((item) => new Date(item.timestamp).toLocaleTimeString([], { hour: "numeric" })));
      document.querySelector("#forecast-chart-desc").textContent = peakElement.textContent;
      document.querySelector("#forecast-table").innerHTML = forecasts.map((item) => `<tr><td>${new Date(item.timestamp).toLocaleString()}</td><td>${item.pm25.toFixed(1)} µg/m³</td><td>${item.aqi}</td><td>${localizedCategory(item.category)}</td></tr>`).join("");
      forecastLoaded = true;
    } catch (_) {
      peakElement.textContent = document.documentElement.lang === "es" ? "No se pudo cargar el pronóstico." : "Forecast could not be loaded.";
      document.querySelector("#forecast-callout").hidden = false;
      document.querySelector("#forecast-action").hidden = true;
    }
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
  document.querySelector("[role=tablist]").addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    const tabs = [...document.querySelectorAll("[data-tab]")];
    const next = (tabs.indexOf(document.activeElement) + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    tabs[next].click();
    event.preventDefault();
  });
})();
