// static/js/onesignal-init.js
(function () {
    'use strict';

    // Verificar que estamos en HTTPS (excepto localhost)
    if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
        console.warn('OneSignal requiere HTTPS para funcionar');
        return;
    }

    window.OneSignalDeferred = window.OneSignalDeferred || [];

    // Función para guardar Player ID en backend
    function savePlayerId(playerId) {
        if (!playerId) {
            console.warn('OneSignal: No Player ID to save');
            return;
        }

        console.log('OneSignal: Guardando Player ID:', playerId.substring(0, 20) + '...');

        fetch('/api/notifications/save-player-id/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ player_id: playerId })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('✅ OneSignal Player ID guardado exitosamente');
                } else {
                    console.error('❌ Error guardando Player ID:', data.error);
                }
            })
            .catch(error => {
                console.error('❌ Error en request save-player-id:', error);
            });
    }

    // Función para obtener CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Verificar estado actual de permisos
    function checkNotificationPermission() {
        if (!('Notification' in window)) {
            console.warn('Este navegador no soporta notificaciones push');
            return 'unsupported';
        }
        return Notification.permission; // 'granted', 'denied', 'default'
    }

    // Función global para activar notificaciones
    window.activateNotifications = function (btnElement) {
        const permissionStatus = checkNotificationPermission();

        // Si ya están bloqueadas, mostrar instrucciones
        if (permissionStatus === 'denied') {
            showBlockedInstructions();
            return;
        }

        // Si no son soportadas
        if (permissionStatus === 'unsupported') {
            alert('❌ Tu navegador no soporta notificaciones push. Por favor usa Chrome, Firefox, Safari o Edge actualizado.');
            return;
        }

        // Feedback visual
        let originalText = '';
        if (btnElement) {
            originalText = btnElement.innerHTML;
            btnElement.disabled = true;
            btnElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Activando...';
        }

        const globalLoader = document.getElementById('globalLoader');
        if (globalLoader) globalLoader.classList.add('active');

        // Solicitar permiso
        if (window.OneSignalDeferred) {
            window.OneSignalDeferred.push(function (OneSignal) {
                OneSignal.Notifications.requestPermission()
                    .then(function (permission) {
                        console.log("OneSignal Permission result:", permission);

                        if (permission === true || permission === 'granted') {
                            // Éxito
                            if (btnElement) {
                                btnElement.innerHTML = '<i class="fas fa-check"></i> ¡Activado!';
                            }

                            // Ocultar banners de notificación
                            hideNotificationBanners();

                            // Guardar Player ID
                            const playerId = OneSignal.User.PushSubscription.id;
                            if (playerId) {
                                savePlayerId(playerId);
                            }

                            // Recargar después de 1.5 segundos
                            setTimeout(function () {
                                window.location.reload();
                            }, 1500);

                        } else if (permission === false || permission === 'denied') {
                            // Denegado
                            showBlockedInstructions();
                            resetButton(btnElement, originalText);

                        } else {
                            // Dismissed / Default
                            console.log('Usuario cerró el diálogo sin responder');
                            resetButton(btnElement, originalText);
                        }

                        if (globalLoader) globalLoader.classList.remove('active');
                    })
                    .catch(function (error) {
                        console.error('Error solicitando permisos:', error);
                        alert('❌ Error al solicitar permisos de notificación. Intenta nuevamente.');
                        resetButton(btnElement, originalText);
                        if (globalLoader) globalLoader.classList.remove('active');
                    });
            });
        } else {
            resetButton(btnElement, originalText);
            if (globalLoader) globalLoader.classList.remove('active');
            alert('❌ OneSignal no se ha cargado correctamente. Recarga la página e intenta nuevamente.');
        }
    };

    // Mostrar instrucciones para desbloquear
    function showBlockedInstructions() {
        const browser = detectBrowser();
        let instructions = "🔔 Las notificaciones están bloqueadas\n\n";

        if (browser === 'chrome') {
            instructions += "Para activarlas en Chrome:\n" +
                "1. Haz clic en el candado 🔒 o ícono de información ⓘ en la barra de dirección\n" +
                "2. Busca 'Notificaciones' y cámbialo a 'Permitir'\n" +
                "3. Recarga la página";
        } else if (browser === 'firefox') {
            instructions += "Para activarlas en Firefox:\n" +
                "1. Haz clic en el candado 🔒 en la barra de dirección\n" +
                "2. Haz clic en la 'X' junto a 'Bloqueado' en Notificaciones\n" +
                "3. Recarga la página";
        } else if (browser === 'safari') {
            instructions += "Para activarlas en Safari:\n" +
                "1. Ve a Safari > Preferencias > Sitios Web\n" +
                "2. Selecciona 'Notificaciones' en el panel izquierdo\n" +
                "3. Encuentra este sitio y cambia a 'Permitir'\n" +
                "4. Recarga la página";
        } else {
            instructions += "Para activarlas:\n" +
                "1. Haz clic en el ícono junto a la URL\n" +
                "2. Busca la configuración de Notificaciones\n" +
                "3. Cámbialo a 'Permitir'\n" +
                "4. Recarga la página";
        }

        alert(instructions);
    }

    // Detectar navegador
    function detectBrowser() {
        const userAgent = navigator.userAgent.toLowerCase();
        if (userAgent.indexOf('chrome') > -1 && userAgent.indexOf('edg') === -1) return 'chrome';
        if (userAgent.indexOf('firefox') > -1) return 'firefox';
        if (userAgent.indexOf('safari') > -1 && userAgent.indexOf('chrome') === -1) return 'safari';
        return 'other';
    }

    // Ocultar banners de notificación
    function hideNotificationBanners() {
        const bannerIds = [
            'notification-banner',
            'customer-notification-card',
            'provider-notification-alert'
        ];

        bannerIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.style.display = 'none';
            }
        });
    }

    // Resetear botón a estado original
    function resetButton(btnElement, originalText) {
        if (btnElement && originalText) {
            btnElement.disabled = false;
            btnElement.innerHTML = originalText;
        }
    }

    // Inicializar OneSignal
    OneSignalDeferred.push(function (OneSignal) {
        // Obtener App ID desde variable global o elemento en el DOM
        const appId = window.ONESIGNAL_APP_ID || 'ea3b0386-d698-4690-9fbb-9ad3136bb29a';

        console.log('🔔 Inicializando OneSignal con App ID:', appId.substring(0, 20) + '...');

        OneSignal.init({
            appId: appId,
            serviceWorkerPath: '/OneSignalSDKWorker.js', // Asegurar que apunta a la raíz
            serviceWorkerParam: { scope: '/' },
            notifyButton: {
                enable: false, // Usamos nuestros propios botones
            },
            allowLocalhostAsSecureOrigin: true,
        })
            .then(function () {
                console.log('✅ OneSignal inicializado correctamente');

                // Verificar estado de suscripción
                const isOptedIn = OneSignal.User.PushSubscription.optedIn;
                const playerId = OneSignal.User.PushSubscription.id;

                console.log('OneSignal Estado - OptedIn:', isOptedIn, 'PlayerId:', playerId ? playerId.substring(0, 20) + '...' : 'null');

                // Si ya está suscrito, guardar ID
                if (isOptedIn && playerId) {
                    savePlayerId(playerId);
                }
            })
            .catch(function (error) {
                console.error('❌ Error inicializando OneSignal:', error);
            });

        // Escuchar cambios en la suscripción
        OneSignal.User.PushSubscription.addEventListener('change', function (event) {
            console.log('OneSignal: Cambio en suscripción detectado');

            if (event.current && event.current.optedIn && event.current.id) {
                savePlayerId(event.current.id);
            }
        });

        // Sync periódico de Player ID (cada 5 minutos)
        setInterval(function () {
            try {
                const isOptedIn = OneSignal.User.PushSubscription.optedIn;
                const playerId = OneSignal.User.PushSubscription.id;

                if (isOptedIn && playerId) {
                    savePlayerId(playerId);
                }
            } catch (e) {
                console.error('Error en sync periódico:', e);
            }
        }, 5 * 60 * 1000);
    });

    console.log('📱 OneSignal script cargado');

})();