# ADR-0001: Estrategia de descomposición en microservicios

## Estado
Aceptada, 17 de septiembre de 2026

## Contexto
MicroPay opera actualmente un sistema monolítico que impide liberar funcionalidades
de forma ágil y presenta cuellos de botella durante picos de uso. El objetivo de este
proyecto es diseñar e implementar una arquitectura basada en microservicios que aplique
buenas prácticas de escalabilidad, disponibilidad y desacoplamiento, dentro de las
limitaciones de recursos gratuitos de AWS Academy Learner Lab.

Antes de decidir plataforma de cómputo, registro de imágenes o enrutamiento (ADRs
0002-0005), es necesario definir **dónde trazamos las fronteras del dominio**: qué
funcionalidades del monolito se separan, en cuántos servicios, y bajo qué criterio de
cohesión/acoplamiento.

## Decisión
Se descompone el dominio en **dos microservicios independientes**, alineados a bounded
contexts con responsabilidades claramente diferenciadas:

- **Usuarios**: gestión de identidad y datos de cuenta (alta, consulta, actualización
  de perfil).
- **Pagos**: procesamiento y consulta de transacciones.

Criterios aplicados para la frontera:
- **Alta cohesión interna**: cada servicio agrupa operaciones que cambian juntas y
  pertenecen al mismo subdominio de negocio.
- **Bajo acoplamiento entre servicios**: Usuarios y Pagos no comparten esquema de
  datos ni lógica interna; solo se comunican a través de contratos HTTP expuestos
  vía API Gateway.
- **Independencia de despliegue**: cada servicio se conteneriza, se publica en su
  propio repositorio de ECR y se despliega como un Service de ECS independiente,
  de forma que uno puede actualizarse sin afectar al otro.
- **Alcance mínimo viable**: se limita a 2 servicios porque es el mínimo que exige
  la evaluación y porque valida el patrón de desacoplamiento sin sobre-diseñar un
  dominio de negocio ficticio.

## Alternativas consideradas

| Alternativa | Por qué se descarta |
|---|---|
| Mantener el monolito, solo contenerizado | No cumple el objetivo central de la evaluación (desacoplamiento y escalabilidad independiente por dominio) |
| Descomponer en 3+ servicios (ej. sumar Notificaciones o Autenticación como servicio aparte) | Fuera del alcance mínimo solicitado; se documenta como evolución futura (ver sección Consecuencias) |
| Separar Usuarios y Pagos pero con una única base de datos compartida | Reintroduce acoplamiento a nivel de datos, contradiciendo el principio de independencia de despliegue |

## Consecuencias

**Positivas**
- Cada servicio puede escalar de forma independiente según su carga (ej. Pagos
  puede recibir más tráfico en picos que Usuarios).
- Fallos aislados: un error en Pagos no tumba el servicio de Usuarios.
- Ciclos de despliegue independientes, resolviendo el problema original de
  liberación ágil de funcionalidades.

**Negativas / trade-offs**
- Se introduce complejidad operacional (dos servicios que monitorear, dos
  pipelines de imagen en ECR en vez de uno).
- La comunicación entre servicios pasa de ser una llamada en memoria (monolito) a
  una llamada de red vía API Gateway, con la latencia y los posibles puntos de
  falla que eso implica.
- No hay transacciones distribuidas entre Usuarios y Pagos en esta iteración; se
  asume que no hay operaciones que requieran consistencia fuerte cruzada entre
  ambos servicios dentro del alcance de la evaluación.

## Alineación con AWS Well-Architected Framework
- **Operational Excellence**: despliegues independientes por servicio reducen el
  radio de impacto de cada cambio.
- **Reliability**: el aislamiento de fallos evita que un microservicio degradado
  afecte al resto del sistema.
- **Performance Efficiency**: permite dimensionar recursos de cómputo de forma
  diferenciada por servicio según su patrón de carga real (se detalla en ADR-0002).
- Security y Cost Optimization se abordan en los ADRs 0002-0005, donde hay
  decisiones técnicas concretas que los afectan directamente.

## Brecha entre diseño ideal y AWS Academy Learner Lab
- **Ideal**: patrón *database-per-service*, con persistencia dedicada por
  microservicio, y comunicación asíncrona (ej. Amazon SNS/SQS) para eventos entre
  Usuarios y Pagos, logrando consistencia eventual sin acoplar los servicios en
  tiempo real.
- **Esta iteración**: la evaluación no exige persistencia de datos (solo validar
  funcionamiento vía llamadas HTTP y logs en CloudWatch), por lo que ambos
  servicios operan sin base de datos propia y la comunicación se mantiene
  síncrona a través de API Gateway. Se documenta como límite de alcance y
  oportunidad de evolución, no como decisión de diseño ideal.
- Se mantiene la restricción ya conocida de Learner Lab: `iam:CreateRole` está
  bloqueado, por lo que ambos servicios usarán `LabRole` como rol de ejecución
  (se detalla en ADR-0002).

## RTO/RPO objetivo
- **RTO**: < 5 minutos, tiempo estimado de recuperación ante fallo de una tarea,
  cubierto por el reemplazo automático de tareas de ECS Fargate (sin intervención
  manual), detallado en ADR-0002.
- **RPO**: No aplica en esta iteración, ningún servicio persiste datos con
  estado, por lo que no existe pérdida de datos que mitigar.

## Costo
La descomposición en sí no tiene costo directo (es una decisión de diseño), pero
cada microservicio adicional implica una tarea de Fargate, un repositorio ECR y
rutas propias en API Gateway, el análisis cuantitativo de costo por servicio se
documenta en ADR-0002 (plataforma de cómputo).

## Referencias
- AWS Well-Architected Framework - Reliability Pillar
- AWS Whitepaper: Implementing Microservices on AWS