---
---

# Login

<div id="result"></div>

<script>

    const url = new URL(window.location.href);
    const error = url.searchParams.get('error');
    const code = url.searchParams.get('code');
    // get previous page

    if (error) {
        let errorText = '';
        errorText = '<h3>Error</h3>';
        // if we have previous, action the user to try again. If not then tell them to go back and try again
            errorText += `<p>There was an error logging you in. Please go back and try again.</p>`;
        document.getElementById('result').innerHTML = errorText;
    } else if (code) {
        let successText = '';
        successText = '<h3>Success</h3>';
        successText += '<p>Login successful. Please copy the code below and paste it into the client.</p>';
        successText += `<input type="text" value="${code}" readonly>`;
        // make a button to copy the code to clipboard
        successText += `<button onclick="navigator.clipboard.writeText('${code}')">Copy to clipboard</button>`;
        document.getElementById('result').innerHTML = successText;
    }

</script>

