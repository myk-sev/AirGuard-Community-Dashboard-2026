let time_last_updated = document.querySelector('#last-updated').textContent;

if (time_last_updated != null) {
    setTimeout(function() {
        let prompt_text = ""
        if (document.documentElement.lang == "en") {
            prompt_text = "Sensor info may be out of date. Reloading the page is recommended. Click 'OK' to reload.";
        }
        else {
            let prompt_text = "La información del sensor puede estar desactualizada. Se recomienda recargar la página. Haz clic en 'OK' para recargar.";
        }

        if (confirm(prompt_text)) {
            location.reload();
        }
    }, parseInt(3600 + time_last_updated - Date.now()));
}
