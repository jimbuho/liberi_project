// Modal para vista detallada de proveedor
function showProviderDetail(providerId) {
    // Crear modal si no existe
    let modal = document.getElementById('providerDetailModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'providerDetailModal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Detalles del Proveedor</h2>
                    <span class="close" onclick="closeProviderDetail()">&times;</span>
                </div>
                <div id="providerDetailContent">
                    <p style="text-align: center;">Cargando...</p>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    // Mostrar modal
    modal.style.display = 'block';
    
    // Cargar datos vía AJAX
    fetch(`/admin/core/providerprofile/${providerId}/detail-ajax/`)
        .then(response => response.json())
        .then(data => {
            const content = document.getElementById('providerDetailContent');
            content.innerHTML = `
                <div class="detail-section">
                    <h3>📋 Información General</h3>
                    <p><strong>Nombre:</strong> ${data.name}</p>
                    <p><strong>Email:</strong> ${data.email}</p>
                    <p><strong>Teléfono:</strong> ${data.phone}</p>
                    <p><strong>Categoría:</strong> ${data.category}</p>
                    <p><strong>Estado:</strong> ${data.status} ${data.is_active ? '🟢' : '🔴'}</p>
                    <p><strong>Descripción:</strong> ${data.description}</p>
                    <p><strong>Costo de viaje:</strong> $${data.avg_travel_cost.toFixed(2)}</p>
                    <p><strong>Registrado:</strong> ${data.created_at}</p>
                </div>
                
                <div class="detail-section">
                    <h3>📍 Zonas de Cobertura</h3>
                    <div class="zone-tags">
                        ${data.zones.length > 0 
                            ? data.zones.map(z => `<span class="zone-tag">${z}</span>`).join('')
                            : '<p>Sin zonas configuradas</p>'
                        }
                    </div>
                </div>
                
                <div class="detail-section">
                    <h3>💼 Servicios</h3>
                    <div class="service-list">
                        ${data.services.length > 0
                            ? data.services.map(s => `
                                <div class="service-card">
                                    <strong>${s.name}</strong><br>
                                    <small>$${s.price} - ${s.duration} min</small><br>
                                    <small>${s.available ? '✅ Disponible' : '❌ No disponible'}</small>
                                </div>
                            `).join('')
                            : '<p>Sin servicios configurados</p>'
                        }
                    </div>
                </div>
                
                <div class="detail-section">
                    <h3>📄 Documentos</h3>
                    <div class="document-grid">
                        ${data.documents.contract 
                            ? `<div class="document-item">
                                <strong>Contrato Firmado</strong>
                                <a href="${data.documents.contract}" target="_blank">
                                    <img src="${data.documents.contract}" alt="Contrato">
                                </a>
                                <a href="${data.documents.contract}" target="_blank" class="button">Ver completo</a>
                            </div>`
                            : '<div class="document-item"><strong>Contrato</strong><br>❌ No cargado</div>'
                        }
                        ${data.documents.id_front
                            ? `<div class="document-item">
                                <strong>Cédula (Frente)</strong>
                                <a href="${data.documents.id_front}" target="_blank">
                                    <img src="${data.documents.id_front}" alt="Cédula frontal">
                                </a>
                                <a href="${data.documents.id_front}" target="_blank" class="button">Ver completo</a>
                            </div>`
                            : '<div class="document-item"><strong>Cédula (Frente)</strong><br>❌ No cargado</div>'
                        }
                        ${data.documents.id_back
                            ? `<div class="document-item">
                                <strong>Cédula (Reverso)</strong>
                                <a href="${data.documents.id_back}" target="_blank">
                                    <img src="${data.documents.id_back}" alt="Cédula posterior">
                                </a>
                                <a href="${data.documents.id_back}" target="_blank" class="button">Ver completo</a>
                            </div>`
                            : '<div class="document-item"><strong>Cédula (Reverso)</strong><br>❌ No cargado</div>'
                        }
                    </div>
                </div>
            `;
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('providerDetailContent').innerHTML = 
                '<p style="color: red; text-align: center;">Error cargando datos del proveedor</p>';
        });
}

function closeProviderDetail() {
    document.getElementById('providerDetailModal').style.display = 'none';
}

// Cerrar modal al hacer clic fuera
window.onclick = function(event) {
    const modal = document.getElementById('providerDetailModal');
    if (event.target === modal) {
        modal.style.display = 'none';
    }
}