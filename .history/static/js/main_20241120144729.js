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

    async function displayResults(data) {
        // Position upload container to the left
        const uploadContainer = document.querySelector('.upload-container');
        uploadContainer.classList.add('positioned');
        
        // Convert JSON to markdown
        const markdown = convertToMarkdown(data);
        
        // Update content
        markdownContent.textContent = markdown;
        jsonContent.textContent = JSON.stringify(data, null, 2);

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

    function convertToMarkdown(data) {
        let markdown = `# Receipt Details\n\n`;
        
        // Handle error handling section
        if (data.error_handling) {
            markdown += `## Error Handling\n`;
            markdown += `- Error Status: ${data.error_handling.has_errors ? 'Has Errors' : 'No Errors'}\n`;
            if (data.error_handling.errors && data.error_handling.errors.length > 0) {
                markdown += `- Errors Found:\n`;
                data.error_handling.errors.forEach(error => {
                    markdown += `  - ID: ${error.id}\n`;
                    markdown += `  - Message: ${error.message}\n`;
                    markdown += `  - Analysis: ${error.analysis}\n`;
                });
            }
            markdown += '\n';
        }

        // Handle basic invoice details
        markdown += `## Invoice Details\n`;
        if (data.invoice_date) markdown += `- Date: ${data.invoice_date}\n`;
        if (data.invoice_number) markdown += `- Invoice Number: ${data.invoice_number}\n`;
        if (data.currency) markdown += `- Currency: ${data.currency}\n`;
        if (data.amount_payable) markdown += `- Amount Payable: ${data.currency} ${data.amount_payable}\n`;
        markdown += '\n';

        // Handle suppliers section
        if (data.suppliers && data.suppliers.length > 0) {
            markdown += `## Suppliers\n`;
            data.suppliers.forEach((supplier, index) => {
                markdown += `### ${supplier.supplier}\n`;
                if (supplier.observation) markdown += `${supplier.observation}\n\n`;
                if (supplier.high_tax_base) markdown += `- High Tax Base: ${data.currency} ${supplier.high_tax_base}\n`;
                if (supplier.high_tax) markdown += `- High Tax Amount: ${data.currency} ${supplier.high_tax}\n`;
                if (supplier.low_tax_base) markdown += `- Low Tax Base: ${data.currency} ${supplier.low_tax_base}\n`;
        for (const [key, value] of Object.entries(data)) {
            if (typeof value === 'object' && value !== null) {
                markdown += `## ${key}\n`;
                for (const [subKey, subValue] of Object.entries(value)) {
                    if (subValue !== null) {
                        markdown += `- **${subKey}**: ${JSON.stringify(subValue)}\n`;
                    }
                }
            } else if (value !== null) {
                markdown += `- **${key}**: ${value}\n`;
            }
        }
        
        return markdown;
    }

    function initializeCopyButtons() {
        document.querySelectorAll('.copy-btn').forEach(btn => {
            btn.addEventListener('click', handleCopy);
        });
    }

    function handleCopy(e) {
        const section = e.target.closest('.result-section');
        const content = section.querySelector('pre').textContent;
        
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