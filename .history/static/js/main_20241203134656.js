document.addEventListener('DOMContentLoaded', function() {
    // PDF.js initialization
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    // PDF preview state variables
    let pdfDoc = null;
    let pageNum = 1;
    let pageRendering = false;
    let pageNumPending = null;
    const scale = 1.5;

    // Get existing DOM elements
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    
    // Get PDF preview elements
    const canvas = document.getElementById('pdfCanvas');
    const ctx = canvas.getContext('2d');
    const prevButton = document.getElementById('prevPage');
    const nextButton = document.getElementById('nextPage');
    const currentPageSpan = document.getElementById('currentPage');
    const totalPagesSpan = document.getElementById('totalPages');
    const pdfPreview = document.getElementById('pdfPreview');

    // PDF rendering functions
    function renderPage(num) {
        pageRendering = true;
        pdfDoc.getPage(num).then(function(page) {
            const viewport = page.getViewport({scale: scale});
            canvas.height = viewport.height;
            canvas.width = viewport.width;

            const renderContext = {
                canvasContext: ctx,
                viewport: viewport
            };

            const renderTask = page.render(renderContext);

            renderTask.promise.then(function() {
                pageRendering = false;
                if (pageNumPending !== null) {
                    renderPage(pageNumPending);
                    pageNumPending = null;
                }
            });
        });

        currentPageSpan.textContent = num;
    }

    function queueRenderPage(num) {
        if (pageRendering) {
            pageNumPending = num;
        } else {
            renderPage(num);
        }
    }

    function showPrevPage() {
        if (pageNum <= 1) {
            return;
        }
        pageNum--;
        queueRenderPage(pageNum);
        updateButtonStates();
    }

    function showNextPage() {
        if (pageNum >= pdfDoc.numPages) {
            return;
        }
        pageNum++;
        queueRenderPage(pageNum);
        updateButtonStates();
    }

    function updateButtonStates() {
        prevButton.disabled = pageNum <= 1;
        nextButton.disabled = pageNum >= pdfDoc.numPages;
    }

    function loadPDF(file) {
        const fileReader = new FileReader();
        
        fileReader.onload = function() {
            const typedarray = new Uint8Array(this.result);

            pdfjsLib.getDocument(typedarray).promise.then(function(pdf) {
                pdfDoc = pdf;
                totalPagesSpan.textContent = pdf.numPages;
                
                // Initial page render
                pageNum = 1;
                renderPage(pageNum);
                updateButtonStates();
                
                // Show PDF preview section
                pdfPreview.classList.remove('hidden');
            }).catch(function(error) {
                console.error('Error loading PDF:', error);
                alert('Error loading PDF preview. The file might be corrupted or invalid.');
            });
        };

        fileReader.readAsArrayBuffer(file);
    }

    // Event Listeners for PDF navigation
    prevButton.addEventListener('click', showPrevPage);
    nextButton.addEventListener('click', showNextPage);

    // File Upload Event Handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        const file = e.dataTransfer.files[0];
        if (file && file.type === 'application/pdf') {
            handleFileUpload(file);
        } else {
            alert('Please upload a PDF file.');
        }
    });

    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });

    function handleFileUpload(file) {
        if (file.type === 'application/pdf') {
            // Load PDF preview
            loadPDF(file);
            
            // Create FormData and send to server
            const formData = new FormData();
            formData.append('file', file);

            // Show processing indicator
            document.querySelector('.processing-indicator').classList.remove('hidden');
            document.querySelector('.upload-content').classList.add('hidden');

            fetch('/extract', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Hide processing indicator
                document.querySelector('.processing-indicator').classList.add('hidden');
                document.querySelector('.upload-content').classList.remove('hidden');

                // Show results
                document.querySelector('.results').classList.remove('hidden');
                
                // Convert and display markdown with tables
                const markdown = convertToMarkdown(data);
                document.querySelector('.markdown-content').innerHTML = marked.parse(markdown, {
                    gfm: true,
                    breaks: true,
                    tables: true
                });

                // Format and display JSON
                document.querySelector('.json-content').textContent = formatJsonForDisplay(data);

                // Add visible class for animation
                setTimeout(() => {
                    document.querySelector('.results').classList.add('visible');
                    document.querySelectorAll('.result-section').forEach(section => {
                        section.classList.add('visible');
                    });
                }, 100);
            })
            .catch(error => {
                console.error('Error:', error);
                document.querySelector('.processing-indicator').classList.add('hidden');
                document.querySelector('.upload-content').classList.remove('hidden');
                alert('An error occurred while processing the file.');
            });
        } else {
            alert('Please upload a PDF file.');
        }
    }

    function formatCurrency(amount, currency = 'EUR') {
        if (!amount) return '';
        const num = parseFloat(amount);
        return `${currency} ${num.toLocaleString('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    function convertToMarkdown(data) {
        let markdown = `# Invoice Details\n\n`;
        markdown += '<div class="details-grid">\n\n';

        // Left Column: General and Supplier Information
        markdown += '<div class="details-section">\n\n';
        
        // General Information
        markdown += `## General Information\n\n`;
        markdown += `| Field | Value |\n`;
        markdown += `|-------|-------|\n`;
        markdown += `| Invoice Number | ${data.invoice_number} |\n`;
        markdown += `| Date | ${data.invoice_date} |\n`;
        if (data.due_date) markdown += `| Due Date | ${data.due_date} |\n`;
        markdown += `| Amount Payable | ${formatCurrency(data.amount_payable)} |\n\n`;

        // Supplier Information
        markdown += `## Supplier Information\n\n`;
        markdown += `| Field | Value |\n`;
        markdown += `|-------|-------|\n`;
        markdown += `| Name | ${data.primary_supplier} |\n`;
        if (data.details_supplier) {
            const supplier = data.details_supplier;
            if (supplier.email) markdown += `| Email | \`${supplier.email}\` |\n`;
            if (supplier.address) markdown += `| Address | ${supplier.address} |\n`;
            if (supplier.iban) markdown += `| IBAN | \`${supplier.iban}\` |\n`;
            if (supplier.vat_id) markdown += `| VAT ID | \`${supplier.vat_id}\` |\n`;
            if (supplier.kvk) markdown += `| KVK | ${supplier.kvk} |\n`;
        }
        markdown += '\n</div>\n\n';

        // Right Column: Financial Details and Payment Information
        markdown += '<div class="details-section">\n\n';
        
        // Financial Details
        markdown += `## Financial Details\n\n`;
        markdown += `| Category | Amount |\n`;
        markdown += `|----------|--------|\n`;
        if (data.suppliers && data.suppliers.length > 0) {
            const supplier = data.suppliers[0];  // Assuming first supplier
            if (supplier.high_tax_base) markdown += `| High Tax Base (21%) | ${formatCurrency(supplier.high_tax_base)} |\n`;
            if (supplier.high_tax) markdown += `| High Tax Amount | ${formatCurrency(supplier.high_tax)} |\n`;
            if (supplier.low_tax_base) markdown += `| Low Tax Base (9%) | ${formatCurrency(supplier.low_tax_base)} |\n`;
            if (supplier.low_tax) markdown += `| Low Tax Amount | ${formatCurrency(supplier.low_tax)} |\n`;
            if (supplier.null_tax_base) markdown += `| Null Tax Base (0%) | ${formatCurrency(supplier.null_tax_base)} |\n`;
            if (supplier.amount_excl_tax) markdown += `| Amount Excluding Tax | ${formatCurrency(supplier.amount_excl_tax)} |\n`;
        }
        if (data.total_emballage) markdown += `| Total Emballage | ${formatCurrency(data.total_emballage)} |\n`;
        markdown += `| **Total Amount Payable** | **${formatCurrency(data.amount_payable)}** |\n\n`;

        // Payment Information
        markdown += `## Payment Information\n\n`;
        markdown += `| Field | Value |\n`;
        markdown += `|-------|-------|\n`;
        if (data.method_of_payment) markdown += `| Payment Method | ${data.method_of_payment} |\n`;
        if (data.recipient) markdown += `| Recipient | ${data.recipient} |\n`;
        
        markdown += '\n</div>\n\n';
        markdown += '</div>\n\n';  // Close details-grid

        // Error handling section if there are errors (full width, below the grid)
        if (data.error_handling?.has_errors) {
            markdown += `## ⚠️ Validation Errors\n\n`;
            if (data.error_handling.errors?.length > 0) {
                data.error_handling.errors.forEach(error => {
                    markdown += `### Error ${error.id}\n`;
                    markdown += `**Message:** ${error.message}\n\n`;
                    markdown += `**Analysis:** ${error.analysis}\n\n`;
                });
            }
        }

        return markdown;
    }

    function formatJsonForDisplay(data) {
        // Deep clone the data to avoid modifying the original
        const formattedData = JSON.parse(JSON.stringify(data));
        
        // Format currency values
        function formatCurrencyInObject(obj) {
            for (let key in obj) {
                if (typeof obj[key] === 'object' && obj[key] !== null) {
                    formatCurrencyInObject(obj[key]);
                } else if (
                    typeof obj[key] === 'string' && 
                    !isNaN(obj[key]) && 
                    (
                        key.includes('amount') ||
                        key.includes('tax') ||
                        key.includes('base') ||
                        key.includes('emballage')
                    )
                ) {
                    obj[key] = parseFloat(obj[key]).toLocaleString('nl-NL', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    });
                }
            }
        }
        
        formatCurrencyInObject(formattedData);
        
        // Return formatted JSON string with proper indentation
        return JSON.stringify(formattedData, null, 2);
    }

    // Copy button functionality
    document.querySelectorAll('.copy-btn').forEach(button => {
        button.addEventListener('click', function() {
            const content = this.closest('.result-section').querySelector('pre').textContent;
            navigator.clipboard.writeText(content).then(() => {
                const originalText = this.textContent;
                this.textContent = 'Copied!';
                setTimeout(() => {
                    this.textContent = originalText;
                }, 2000);
            });
        });
    });

    // Download button functionality
    document.querySelectorAll('.download-btn').forEach(button => {
        button.addEventListener('click', function() {
            const content = this.closest('.result-section').querySelector('pre').textContent;
            const isJSON = this.closest('.result-section').classList.contains('json-section');
            const filename = `extracted_${isJSON ? 'data.json' : 'text.md'}`;
            
            const blob = new Blob([content], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        });
    });
}); 