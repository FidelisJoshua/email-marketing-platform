document.addEventListener("DOMContentLoaded", function () {

    /*
     * Automatically hide flash messages
     * after a few seconds.
     */

    const alerts = document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {

        setTimeout(function () {

            alert.style.transition = "opacity 0.4s";
            alert.style.opacity = "0";

            setTimeout(function () {
                alert.remove();
            }, 400);

        }, 5000);

    });


    /*
     * Simple contact/campaign search.
     */

    const searchInput = document.querySelector(".search-input");

    if (searchInput) {

        searchInput.addEventListener("input", function () {

            const value = this.value.toLowerCase();

            const rows = document.querySelectorAll(
                ".custom-table tbody tr"
            );

            rows.forEach(function (row) {

                row.style.display =
                    row.textContent.toLowerCase().includes(value)
                    ? ""
                    : "none";

            });

        });

    }

});