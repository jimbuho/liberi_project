from django.core.management.base import BaseCommand
from legal.models import LegalDocument


class Command(BaseCommand):
    help = 'Crea los documentos legales iniciales (Términos y Privacidad)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Creando documentos legales...\n'))

        documents = [
            {
                'document_type': 'terms_user',
                'name': 'Términos de Uso - Usuario',
                'content': '''
                    <h1>Términos y Condiciones de Uso — Usuario</h1>
                    <p><strong>Última actualización: 2025-11-12</strong></p>

                    <h4>1. Aceptación</h4>
                    <p>El acceso y uso del sitio y servicios de <strong>Liberi</strong> implica la aceptación expresa y sin reservas de estos Términos. Si no está de acuerdo, no utilice la plataforma.</p>

                    <h4>2. Objeto</h4>
                    <p>Liberi es una plataforma tecnológica que facilita la conexión entre usuarios y proveedores de servicios a domicilio (belleza, limpieza y otros) para la búsqueda, reserva y pago de servicios.</p>

                    <h4>3. Uso permitido</h4>
                    <ul>
                        <li>Usar la plataforma conforme a la ley y a su finalidad.</li>
                        <li>No intentar vulnerar, replicar, modificar o realizar ingeniería inversa del software.</li>
                        <li>No revender servicios ni utilizar la plataforma para fines ilícitos.</li>
                    </ul>

                    <h4>4. Registro y veracidad</h4>
                    <p>El usuario garantiza que la información proporcionada es veraz. Si se detecta información falsa o fraudulenta, Liberi se reserva suspender o eliminar la cuenta.</p>

                    <h4>5. Responsabilidad</h4>
                    <p>Liberi actúa como intermediario tecnológico. No es responsable directo por la ejecución del servicio contratado entre usuario y proveedor. Las reclamaciones por prestación del servicio deben dirigirse al proveedor y, cuando corresponda, a Liberi para mediar.</p>

                    <h4>6. Propiedad intelectual</h4>
                    <p>Todos los derechos del software, marca y contenidos pertenecen a Liberi. Queda prohibida su copia, redistribución o explotación no autorizada.</p>

                    <h4>7. Incumplimiento y sanciones</h4>
                    <p>El incumplimiento de estos términos puede derivar en suspensión, bloqueo o eliminación de la cuenta, y en la eventual denuncia ante autoridades competentes.</p>

                    <h4>8. Cambios</h4>
                    <p>Liberi podrá modificar estos términos. Las versiones se publicarán en la plataforma y los usuarios serán notificados cuando sea relevante.</p>
                '''
            },
            {
                'document_type': 'privacy_user',
                'name': 'Política de Privacidad - Usuario',
                'content': '''
                    <h1>Política de Privacidad — Usuario</h1>
                    <p><strong>Última actualización: 2025-11-12</strong></p>

                    <h4>1. Responsable del Tratamiento</h4>
                    <p><strong>Liberi</strong> es responsable del tratamiento de los datos personales recopilados en esta plataforma.</p>

                    <h4>2. Datos recolectados</h4>
                    <ul>
                        <li>Identificación: nombres, email, teléfono.</li>
                        <li>Datos de localización y direcciones de servicio.</li>
                        <li>Datos de transacciones: historial de reservas, pagos y facturación.</li>
                        <li>Datos técnicos: IP, user-agent, registros de acceso.</li>
                    </ul>

                    <h4>3. Finalidades</h4>
                    <p>Los datos se usan para: crear cuentas, gestionar reservas y pagos, verificar identidad, prevenir fraude, comunicación transaccional y cumplimiento legal.</p>

                    <h4>4. Base legal</h4>
                    <p>El tratamiento se realiza con el consentimiento del titular y cuando sea necesario para la ejecución de un contrato o cumplimiento de obligaciones legales, conforme a la Ley Orgánica de Protección de Datos Personales del Ecuador.</p>

                    <h4>5. Derechos del titular</h4>
                    <p>Los usuarios pueden ejercer derechos de acceso, rectificación, supresión, oposición y portabilidad enviando solicitud a soporte@liberi.ec. Las solicitudes serán tramitadas según la normativa y plazos legales.</p>

                    <h4>6. Seguridad</h4>
                    <p>Liberi aplica medidas técnicas y organizativas alineadas con ISO/IEC 27701 e ISO/IEC 27001: cifrado en tránsito y reposo, control de accesos, registros de auditoría y pruebas de seguridad.</p>

                    <h4>7. Transferencias y almacenamiento</h4>
                    <p>Los datos pueden almacenarse en servicios de terceros. Liberi garantizará cláusulas contractuales para asegurar un nivel de protección equivalente.</p>

                    <h4>8. Conservación</h4>
                    <p>Los datos se conservarán mientras la cuenta esté activa y durante los plazos legales requeridos.</p>
                '''
            },
            {
                'document_type': 'terms_provider',
                'name': 'Términos de Uso - Proveedor',
                'content': '''
                    <h1>Términos de Uso y Contrato — Proveedor</h1>
                    <p><strong>Última actualización: 2025-11-12</strong></p>

                    <h4>1. Aceptación y Contrato</h4>
                    <p>Para ofrecer servicios en Liberi, el proveedor debe aceptar estos términos y suscribir un contrato con Liberi (digital o físico). El contrato obliga al proveedor a brindar información veraz y prestar servicios lícitos.</p>

                    <h4>2. Declaraciones del Proveedor</h4>
                    <ul>
                        <li>El proveedor declara su identidad, acreditaciones y experiencia reales y verificables.</li>
                        <li>No ofrecerá servicios relacionados con actividades ilícitas.</li>
                    </ul>

                    <h4>3. Obligaciones</h4>
                    <ul>
                        <li>Cumplir con las reservas confirmadas.</li>
                        <li>Cumplir la normativa local y sanitaria aplicable al servicio.</li>
                        <li>Tratar la información de clientes conforme a la ley de protección de datos.</li>
                    </ul>

                    <h4>4. Documentación y verificación</h4>
                    <p>Liberi podrá requerir copia de cédula, certificaciones, RUC, cuenta bancaria y certificados sanitarios. La falta de verificación puede impedir la publicación del perfil.</p>

                    <h4>5. Sanciones</h4>
                    <p>Incumplimientos pueden derivar en suspensión, eliminación, retención de pagos y notificación a autoridades. Liberi podrá retener fondos cuando existan indicios de fraude o ilegalidad.</p>

                    <h4>6. Propiedad Intelectual y Restricciones Técnicas</h4>
                    <p>Queda prohibido usar scripts, bots, scraping o duplicación de información. El proveedor no adquiere derechos sobre la plataforma ni sus datos.</p>
                '''
            },
            {
                'document_type': 'privacy_provider',
                'name': 'Política de Privacidad - Proveedor',
                'content': '''
                    <h1>Política de Privacidad — Proveedor</h1>
                    <p><strong>Última actualización: 2025-11-12</strong></p>

                    <h4>1. Datos recolectados</h4>
                    <ul>
                        <li>Identificación: nombres, cédula / RUC, dirección, teléfono, email.</li>
                        <li>Información profesional: experiencia, certificaciones, fotografías y portafolio.</li>
                        <li>Datos bancarios para pagos.</li>
                        <li>Documentos de soporte (contratos, permisos, certificados).</li>
                    </ul>

                    <h4>2. Finalidades</h4>
                    <p>Validación de identidad, gestión de pagos, cumplimiento fiscal, control de calidad y prevención de riesgos/actividades ilícitas.</p>

                    <h4>3. Transferencias</h4>
                    <p>Los datos pueden almacenarse en proveedores (Supabase, AWS). Liberi asegurará cláusulas contractuales y medidas técnicas acordes a ISO/IEC 27701.</p>

                    <h4>4. Seguridad y Retención</h4>
                    <p>Se aplican controles de acceso, cifrado y registros de auditoría. Los datos se conservan durante la relación contractual y por los plazos legales necesarios.</p>

                    <h4>5. Derechos</h4>
                    <p>Los proveedores pueden ejercer derechos ARCO y solicitudes dirigidas a legal@liberi.ec.</p>
                '''
            }
        ]

        created_count = 0
        skipped_count = 0

        for doc_data in documents:
            doc_type = doc_data['document_type']
            name = doc_data['name']
            content = doc_data['content']

            try:
                # Intentar obtener o crear
                doc, created = LegalDocument.objects.get_or_create(
                    document_type=doc_type,
                    version=1,
                    defaults={
                        'content': content,
                        'status': 'published',
                        'is_active': True,
                    }
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ CREADO: {name} (v1)')
                    )
                    created_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⏭️  EXISTE: {name} (v1)')
                    )
                    skipped_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ ERROR en {name}: {str(e)}')
                )

        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(
                f'✨ COMPLETADO: {created_count} creados, {skipped_count} omitidos'
            )
        )
        self.stdout.write('='*60 + '\n')