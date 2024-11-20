document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const results = document.querySelector('.results');
    const uploadBtn = document.querySelector('.upload-btn');
    const markdownContent = document.querySelector('.markdown-content');
    const jsonContent = document.querySelector('.json-content');

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
        if (file && (file.type === 'text/plain' || file.name.endsWith('.txt'))) {
            processFile(file);
        } else {
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
            dropZone.classList.add('processing');

            const response = await fetch('/extract', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Failed to process receipt');

            const data = await response.json();
            
            // Remove processing state
            dropZone.classList.remove('processing');
            
            // Display results with staggered animations
            await displayResults(data);

        } catch (error) {
            console.error('Error:', error);
            alert('Error processing receipt. Please try again.');
            dropZone.classList.remove('processing');
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
        let markdown = '# Receipt Details\n\n';
        
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
    function createRipple(event) {
        const button = event.currentTarget;
        const circle = document.createElement('span');
        const diameter = Math.max(button.clientWidth, button.clientHeight);
        
        circle.style.width = circle.style.height = `${diameter}px`;
        circle.style.left = `${event.clientX - button.offsetLeft - diameter / 2}px`;
        circle.style.top = `${event.clientY - button.offsetTop - diameter / 2}px`;
        circle.classList.add('ripple');
        
        button.appendChild(circle);
        setTimeout(() => circle.remove(), 600);
    }
}); 