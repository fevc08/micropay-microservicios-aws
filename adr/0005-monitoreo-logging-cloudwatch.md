# ADR-0005: Estrategia de monitoreo y logging con Amazon CloudWatch

## Estado
Aceptada, 17 de septiembre de 2026

## Contexto
Los microservicios Usuarios y Pagos corren en tareas de ECS Fargate (ADR-0002),
expuestas a través de dos ALB y un API Gateway común (ADR-0004). La consigna
exige monitoreo básico con CloudWatch Logs, con evidencia de logs visibles como
parte de la validación de la evaluación. Es necesario definir cómo se organizan
los logs de cada componente y qué nivel de observabilidad adicional (métricas,
alarmas) tiene sentido dentro del alcance del proyecto.

## Decisión
Se centraliza toda la observabilidad en **Amazon CloudWatch**, con logging
diferenciado por componente:

**Log Groups de aplicación (uno por microservicio):**
- `/ecs/micropay/usuarios`
- `/ecs/micropay/pagos`

Cada Task Definition usa el log driver `awslogs`, configurado con:
- `awslogs-group`: el log group correspondiente al servicio.
- `awslogs-region`: región activa del Learner Lab.
- `awslogs-stream-prefix`: `ecs` (genera un log stream por tarea, identificable
  por su Task ID).

**Retención**: 3 días en ambos log groups, suficiente para cubrir la ventana de
trabajo de la evaluación sin acumular costo de almacenamiento innecesario en un
entorno que se destruirá al finalizar.

**Logs de acceso del ALB**: se habilita *access logging* en ambos Application
Load Balancers hacia un bucket S3 dedicado (`micropay-alb-logs-<account-id>`),
para tener evidencia de las solicitudes HTTP a nivel de balanceador, complementaria
a los logs de aplicación.

**Métricas y alarma mínima**: se configura una alarma de CloudWatch sobre
`ECSServiceAverageCPUUtilization` por servicio, con umbral > 80% durante 2
períodos consecutivos de 1 minuto, notificando a un tópico SNS, esto además
sirve como evidencia visual de que la política de Auto Scaling (ADR-0002) tiene
una señal de monitoreo asociada, no solo una configuración declarada.

## Alternativas consideradas

| Alternativa | Por qué se descarta |
|---|---|
| Un único log group compartido para ambos microservicios | Mezcla los logs de Usuarios y Pagos, dificultando el diagnóstico por servicio y contradiciendo la independencia operativa definida en ADR-0001 |
| AWS X-Ray para trazabilidad distribuida entre servicios | Aporta valor real en un sistema con más de dos servicios y llamadas encadenadas complejas; para este alcance (dos servicios, sin llamadas entre sí) el costo de configuración no se justifica frente al beneficio |
| Retención indefinida (`Never expire`) de los log groups | Genera costo de almacenamiento creciente sin beneficio, dado que todos los recursos del proyecto se eliminan al finalizar la sesión de Learner Lab |

## Consecuencias

**Positivas**
- Los logs de cada microservicio son fácilmente identificables y aislados,
  facilitando el diagnóstico dirigido durante las pruebas de validación.
- Los logs de acceso del ALB permiten correlacionar una solicitud HTTP externa
  (vista desde API Gateway) con el comportamiento interno del microservicio
  (visto desde su log group), dando trazabilidad de extremo a extremo.
- La alarma de CPU convierte el Auto Scaling (ADR-0002) en algo observable, no
  solo configurado — se puede demostrar visualmente que el sistema reacciona a
  carga real.

**Negativas / trade-offs**
- El logging de acceso del ALB requiere un bucket S3 adicional con su propia
  política de bucket, sumando un componente más a la arquitectura.
- La alarma de CPU y el tópico SNS son configuración adicional que no es
  estrictamente exigida por la consigna (que solo pide logs visibles), pero se
  incluye para reforzar la evidencia de escalabilidad real.

## Alineación con AWS Well-Architected Framework
- **Operational Excellence**: logs estructurados por servicio permiten
  diagnóstico rápido y aislado ante incidentes.
- **Reliability**: la alarma de CPU provee una señal temprana de saturación,
  antes de que el Auto Scaling llegue a su capacidad máxima configurada.
- **Cost Optimization**: retención corta (3 días) evita costo de almacenamiento
  de logs innecesario en un entorno temporal.

## Brecha entre diseño ideal y AWS Academy Learner Lab
- **Ideal**: dashboards de CloudWatch consolidados por servicio, métricas
  personalizadas de aplicación (ej. tiempo de respuesta por endpoint, tasa de
  error 5xx) además de las métricas de infraestructura, y alarmas conectadas a
  un canal de notificación real (email o Slack) mediante SNS.
- **Esta iteración**: se implementan métricas de infraestructura estándar
  (CPU) y logs, sin métricas de aplicación personalizadas ni dashboard
  consolidado, dado que el alcance de la evaluación pide evidencia de logs
  visibles, no un sistema de observabilidad completo. El tópico SNS de la
  alarma puede dejarse sin suscripción activa (solo para demostrar la
  configuración) si no se dispone de un canal de notificación a mano durante
  la sesión.
- No se identifican bloqueos de IAM adicionales para CloudWatch más allá de
  `LabRole` (ADR-0002), que ya incluye los permisos de `logs:CreateLogStream` y
  `logs:PutLogEvents` necesarios por defecto.

## RTO/RPO objetivo
- No aplica directamente: CloudWatch es un componente de observabilidad, no
  está en el camino crítico de disponibilidad del servicio. Una interrupción
  de CloudWatch no afecta la capacidad de Usuarios o Pagos de responder
  solicitudes, solo la visibilidad temporal sobre su comportamiento.

## Costo
CloudWatch Logs cobra por GB ingerido y por GB almacenado, con retención de 3
días y el volumen de tráfico esperado en pruebas, el costo es marginal. El
bucket S3 de logs del ALB tiene un costo de almacenamiento igualmente bajo para
este volumen. La alarma de CloudWatch y el tópico SNS no tienen costo relevante
en este volumen de uso (dentro de los límites gratuitos habituales de ambos
servicios).

## Referencias
- Amazon CloudWatch Logs - Documentación oficial
- Amazon ECS - Using the awslogs log driver
- Elastic Load Balancing - Access logs for your Application Load Balancer