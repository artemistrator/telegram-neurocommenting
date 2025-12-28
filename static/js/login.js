document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    console.log('🔐 Login attempt started...');
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('error');
    
    console.log('📧 Email:', email);
    
    try {
        console.log('📡 Sending request to /api/auth/login...');
        
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email, password })
        });
        
        console.log('📥 Response status:', response.status);
        
        const data = await response.json();
        console.log('📦 Response data:', data);
        
        if (response.ok && data.access_token) {
            console.log('✅ Login successful!');
            // Save to cookies instead of localStorage
            document.cookie = `access_token=${data.access_token}; path=/; max-age=900000`;
            document.cookie = `refresh_token=${data.refresh_token}; path=/; max-age=2592000`;
            
            console.log('🔄 Redirecting to /home...');
            window.location.href = '/home';
        } else {
            console.error('❌ Login failed:', data);
            errorDiv.textContent = data.detail || 'Неверный email или пароль';
            errorDiv.classList.remove('hidden');
        }
    } catch (error) {
        console.error('💥 Network error:', error);
        errorDiv.textContent = 'Ошибка подключения к серверу';
        errorDiv.classList.remove('hidden');
    }
});