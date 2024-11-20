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
        console.log('Validating file:', file);
        if (file && (file.type === 'text/plain' || file.name.endsWith('.txt'))) {
            console.log('File is valid. Processing...');
            processFile(file);
        } else {
            console.log('Invalid file type.');
            alert('Please upload a text (.txt) file');
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

            if (!response.ok) throw new Error(`Failed to process receipt: ${response.statusText}`);

            const data = await response.json();
            console.log('Received data:', data);
            
            // Remove processing state
            processingIndicator.classList.add('hidden');
            
            // Display results with staggered animations
            await displayResults(data);

        } catch (error) {
            console.error('Error:', error);
            alert('Error processing receipt. Please try again.');
            processingIndicator.classList.add('hidden');
        }
    }

    function filterEmptyValues(obj) {
        if (Array.isArray(obj)) {
            return obj.map(filterEmptyValues).filter(item => {
                if (typeof item === 'object') {
                    return Object.keys(item).length > 0;
                }
                return item != null;
            });
        }
        
        if (obj && typeof obj === 'object') {
            const filtered = {};
            Object.entries(obj).forEach(([key, value]) => {
                if (value != null && value !== '' && 
                    !(Array.isArray(value) && value.length === 0) &&
                    !(typeof value === 'object' && Object.keys(value).length === 0)) {
                    filtered[key] = filterEmptyValues(value);
                }
            });
            return filtered;
        }
        
        return obj;
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
}); 