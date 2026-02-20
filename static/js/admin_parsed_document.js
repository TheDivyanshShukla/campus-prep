document.addEventListener('DOMContentLoaded', function () {
    // Wait for Django Admin's jQuery to load
    if (typeof django !== 'undefined' && django.jQuery) {
        (function ($) {
            function toggleYearField() {
                var documentType = $('#id_document_type').val();
                var yearFieldRow = $('.field-year'); // The wrapping div for the year field

                if (documentType === 'PYQ') {
                    yearFieldRow.show();
                } else {
                    yearFieldRow.hide();
                    $('#id_year').val(''); // Clear the year if not applicable
                }
            }

            // Initial check on page load
            toggleYearField();

            // Check whenever the dropdown changes
            $('#id_document_type').change(function () {
                toggleYearField();
            });
        })(django.jQuery);
    }
});
