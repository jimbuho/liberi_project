window.OneSignalDeferred = window.OneSignalDeferred || [];
OneSignalDeferred.push(function (OneSignal) {
    if (window.ONESIGNAL_APP_ID) {
        OneSignal.init({
            appId: window.ONESIGNAL_APP_ID,
            allowLocalhostAsSecureOrigin: true,
            notifyButton: {
                enable: false,
            },
        });
    }
});
