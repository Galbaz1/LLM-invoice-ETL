document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const results = document.querySelector('.results');
    const uploadBtn = document.querySelector('.upload-btn');
    const markdownContent = document.querySelector('.markdown-content');
    const jsonContent = document.querySelector('.json-content');
    const processingIndicator = document.querySelector('.processing-indicator');

    // File upload handling
    uploadBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', handleFileSelect);
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);

    function handleDragOver(e) {
        e.preventDefault();
        dropZone.classList.add('dragover');
    }

    function handleDragLeave(e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
    }

    function handleDrop(e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        validateAndProcessFile(file);
    }

    function handleFileSelect(e) {
        const file = e.target.files[0];
        validateAndProcessFile(file);
    }

    function validateAndProcessFile(file) {
        if (!file) {
            console.error('No file provided');
            alert('Please select a file');
            return;
        }

        console.log('File validation details:', {
            name: file.name,
            type: file.type,
            size: file.size,
            lastModified: new Date(file.lastModified).toISOString()
        });

        // Some browsers might not set the correct MIME type
        const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
        console.log('File extension:', fileExtension);
        
        // Check both MIME type and extension
        const isValidMimeType = ['text/plain', 'application/pdf'].includes(file.type);
        const isValidExtension = ['.txt', '.pdf'].includes(fileExtension);
        
        console.log('Validation results:', {
            mimeType: file.type,
            isValidMimeType,
            fileExtension,
            isValidExtension
        });

        if (isValidMimeType || isValidExtension) {
            console.log('File validation passed');
            processFile(file);
        } else {
            console.error('File validation failed:', {
                mimeType: file.type,
                extension: fileExtension
            });
            alert('Please upload a PDF or TXT file');
        }
    }

    async function processFile(file) {
        if (!file) {
            alert('Please select a file');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            // Reset any previous results
            results.classList.remove('visible');
            results.classList.add('hidden');
            document.querySelectorAll('.result-section').forEach(section => {
                section.classList.remove('visible');
            });

            // Show processing state
            processingIndicator.classList.remove('hidden');

            const response = await fetch('/extract', {
                method: 'POST',
                body: formData
            });

            // Log the full response for debugging
            console.log('Server response:', {
                status: response.status,
                statusText: response.statusText,
                headers: Object.fromEntries(response.headers.entries())
            });

            if (!response.ok) {
                const errorData = await response.json();
                console.error('Server error details:', errorData);
                throw new Error(errorData.detail || `Server error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Received data:', data);
            
            // Remove processing state
            processingIndicator.classList.add('hidden');
            
            // Display results with staggered animations
            await displayResults(data);

        } catch (error) {
            console.error('Request failed:', error);
            // Show a more detailed error message
            const errorMessage = error.message || 'Error processing file. Please try again.';
            console.error('Error details:', {
                message: errorMessage,
                stack: error.stack
            });
            alert(errorMessage);
            processingIndicator.classList.add('hidden');
        }
    }

    function filterEmptyValues(obj) {
        if (Array.isArray(obj)) {
            return obj.map(filterEmptyValues).filter(item => {
                if (typeof item === 'object') {
                    return Object.keys(filterEmptyValues(item)).length > 0;
                }
                return !isEmptyValue(item);
            });
        }
        
        if (obj && typeof obj === 'object') {
            const filtered = {};
            Object.entries(obj).forEach(([key, value]) => {
                if (!isEmptyValue(value)) {
                    const filteredValue = filterEmptyValues(value);
                    if (!isEmptyValue(filteredValue)) {
                        filtered[key] = filteredValue;
                    }
                }
            });
            return filtered;
        }
        
        return obj;
    }

    function isEmptyValue(value) {
        // Check for null, undefined, empty string
        if (value == null || value === '') return true;
        
        // Check for zero values in different formats
        if (typeof value === 'number' || typeof value === 'string') {
            const numValue = Number(value);
            if (!isNaN(numValue) && numValue === 0) return true;
        }
        
        // Check for "0.00" and similar string formats
        if (typeof value === 'string' && /^0*\.?0*$/.test(value)) return true;
        
        // Check for "none" or "None" in different cases
        if (typeof value === 'string' && value.toLowerCase() === 'none') return true;
        
        // Check for empty arrays
        if (Array.isArray(value) && value.length === 0) return true;
        
        // Check for empty objects
        if (typeof value === 'object' && Object.keys(value).length === 0) return true;
        
        return false;
    }

    function convertToMarkdown(data) {
        // Filter out null/empty values first
        const filteredData = filterEmptyValues(data);
        
        let markdown = `# Receipt Details\n\n`;
        
        // Handle error handling section
        if (filteredData.error_handling?.has_errors) {
            markdown += `## Error Handling\n`;
            markdown += `- Error Status: Has Errors\n`;
            if (filteredData.error_handling.errors?.length > 0) {
                markdown += `- Errors Found:\n`;
                filteredData.error_handling.errors.forEach(error => {
                    markdown += `  - ID: ${error.id}\n`;
                    markdown += `  - Message: ${error.message}\n`;
                    markdown += `  - Analysis: ${error.analysis}\n`;
                });
            }
            markdown += '\n';
        }

        // Handle basic invoice details
        if (Object.keys(filteredData).some(key => ['invoice_date', 'invoice_number', 'currency', 'amount_payable'].includes(key))) {
            markdown += `## Invoice Details\n`;
            if (filteredData.invoice_date) markdown += `- Date: ${filteredData.invoice_date}\n`;
            if (filteredData.invoice_number) markdown += `- Invoice Number: ${filteredData.invoice_number}\n`;
            if (filteredData.currency) markdown += `- Currency: ${filteredData.currency}\n`;
            if (filteredData.amount_payable) markdown += `- Amount Payable: ${filteredData.currency} ${filteredData.amount_payable}\n`;
            markdown += '\n';
        }

        // Handle suppliers section
        if (filteredData.suppliers && filteredData.suppliers.length > 0) {
            markdown += `## Suppliers\n`;
            filteredData.suppliers.forEach((supplier, index) => {
                markdown += `### ${supplier.supplier}\n`;
                if (supplier.observation) markdown += `${supplier.observation}\n\n`;
                if (supplier.high_tax_base) markdown += `- High Tax Base: ${filteredData.currency} ${supplier.high_tax_base}\n`;
                if (supplier.high_tax) markdown += `- High Tax Amount: ${filteredData.currency} ${supplier.high_tax}\n`;
                if (supplier.low_tax_base) markdown += `- Low Tax Base: ${filteredData.currency} ${supplier.low_tax_base}\n`;
                if (supplier.low_tax) markdown += `- Low Tax Amount: ${filteredData.currency} ${supplier.low_tax}\n`;
                if (supplier.null_tax_base) markdown += `- Null Tax Base: ${filteredData.currency} ${supplier.null_tax_base}\n`;
                markdown += '\n';
            });
        }

        // Handle supplier details
        if (filteredData.details_supplier) {
            markdown += `## Supplier Details\n`;
            const details = filteredData.details_supplier;
            if (details.email) markdown += `- Email: ${details.email}\n`;
            if (details.address) markdown += `- Address: ${details.address}\n`;
            if (details.iban) markdown += `- IBAN: ${details.iban}\n`;
            if (details.vat_id) markdown += `- VAT ID: ${details.vat_id}\n`;
            if (details.kvk) markdown += `- KVK: ${details.kvk}\n`;
            markdown += '\n';
        }

        // Handle financial details
        markdown += `## Financial Summary\n`;
        if (filteredData.amount_excl_tax) markdown += `- Amount Excluding Tax: ${filteredData.currency} ${filteredData.amount_excl_tax}\n`;
        if (filteredData.high_tax_base) markdown += `- High Tax Base (21%): ${filteredData.currency} ${filteredData.high_tax_base}\n`;
        if (filteredData.high_tax) markdown += `- High Tax Amount: ${filteredData.currency} ${filteredData.high_tax}\n`;
        if (filteredData.low_tax_base) markdown += `- Low Tax Base (9%): ${filteredData.currency} ${filteredData.low_tax_base}\n`;
        if (filteredData.low_tax) markdown += `- Low Tax Amount: ${filteredData.currency} ${filteredData.low_tax}\n`;
        if (filteredData.total_emballage) markdown += `- Total Emballage: ${filteredData.currency} ${filteredData.total_emballage}\n`;
        markdown += '\n';

        // Handle payment details
        markdown += `## Payment Information\n`;
        if (filteredData.recipient) markdown += `- Recipient: ${filteredData.recipient}\n`;
        if (filteredData.method_of_payment) markdown += `- Payment Method: ${filteredData.method_of_payment}\n`;
        if (filteredData.amount_payable_citation) markdown += `- Amount Payable Citation: \`${filteredData.amount_payable_citation}\`\n`;

        return markdown;
    }

    async function displayResults(data) {
        const filteredData = filterEmptyValues(data);
        
        // Position upload container to the left
        const uploadContainer = document.querySelector('.upload-container');
        uploadContainer.classList.add('positioned');
        
        // Convert JSON to markdown and then to HTML
        const markdown = convertToMarkdown(filteredData);
        const htmlContent = marked.parse(markdown); // Convert markdown to HTML
        
        // Update content
        markdownContent.innerHTML = htmlContent;
        jsonContent.textContent = JSON.stringify(filteredData, null, 2);

        // Show results container with animation
        results.classList.remove('hidden');
        
        // Add visible class to results container
        await new Promise(resolve => setTimeout(resolve, 100));
        results.classList.add('visible');
        
        // Add visible class to individual sections with staggered delay
        const markdownSection = document.querySelector('.markdown-section');
        const jsonSection = document.querySelector('.json-section');
        
        await new Promise(resolve => setTimeout(resolve, 200));
        markdownSection.classList.add('visible');
        
        await new Promise(resolve => setTimeout(resolve, 300));
        jsonSection.classList.add('visible');

        // Initialize copy buttons after content is loaded
        initializeCopyButtons();
    }

    function initializeCopyButtons() {
        document.querySelectorAll('.copy-btn').forEach(btn => {
            btn.addEventListener('click', handleCopy);
        });
    }

    function handleCopy(e) {
        const section = e.target.closest('.result-section');
        let content;
        
        if (section.classList.contains('markdown-section')) {
            // For markdown section, get the original markdown text
            content = convertToMarkdown(JSON.parse(jsonContent.textContent));
        } else {
            // For JSON section, get the formatted JSON
            content = section.querySelector('pre').textContent;
        }
        
        navigator.clipboard.writeText(content).then(() => {
            const originalText = e.target.textContent;
            e.target.textContent = '✓ Copied!';
            setTimeout(() => {
                e.target.textContent = originalText;
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
            alert('Failed to copy to clipboard');
        });
    }

    // PDF.js initialization
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    let pdfDoc = null;
    let pageNum = 1;
    let pageRendering = false;
    let pageNumPending = null;
    const scale = 1.5;

    // DOM Elements
    const canvas = document.getElementById('pdfCanvas');
    const ctx = canvas.getContext('2d');
    const prevButton = document.getElementById('prevPage');
    const nextButton = document.getElementById('nextPage');
    const currentPageSpan = document.getElementById('currentPage');
    const totalPagesSpan = document.getElementById('totalPages');
    const pdfPreview = document.getElementById('pdfPreview');
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');

    /**
     * Render the page
     * @param num Page number.
     */
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

    /**
     * Queue rendering of the page
     * @param num Page number.
     */
    function queueRenderPage(num) {
        if (pageRendering) {
            pageNumPending = num;
        } else {
            renderPage(num);
        }
    }

    /**
     * Show previous page.
     */
    function showPrevPage() {
        if (pageNum <= 1) {
            return;
        }
        pageNum--;
        queueRenderPage(pageNum);
        updateButtonStates();
    }

    /**
     * Show next page.
     */
    function showNextPage() {
        if (pageNum >= pdfDoc.numPages) {
            return;
        }
        pageNum++;
        queueRenderPage(pageNum);
        updateButtonStates();
    }

    /**
     * Update button states based on current page
     */
    function updateButtonStates() {
        prevButton.disabled = pageNum <= 1;
        nextButton.disabled = pageNum >= pdfDoc.numPages;
    }

    /**
     * Load and render PDF
     * @param {File} file The PDF file to load
     */
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
            });
        };

        fileReader.readAsArrayBuffer(file);
    }

    // Event Listeners
    prevButton.addEventListener('click', showPrevPage);
    nextButton.addEventListener('click', showNextPage);

    // File Upload Handling
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

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Hide processing indicator
                document.querySelector('.processing-indicator').classList.add('hidden');
                document.querySelector('.upload-content').classList.remove('hidden');

                // Show results
                document.querySelector('.results').classList.remove('hidden');
                document.querySelector('.markdown-content').textContent = data.markdown;
                document.querySelector('.json-content').textContent = JSON.stringify(data.json, null, 2);
            })
            .catch(error => {
                console.error('Error:', error);
                // Hide processing indicator and show error message
                document.querySelector('.processing-indicator').classList.add('hidden');
                document.querySelector('.upload-content').classList.remove('hidden');
                alert('An error occurred while processing the file.');
            });
        } else {
            alert('Please upload a PDF file.');
        }
    }
}); 