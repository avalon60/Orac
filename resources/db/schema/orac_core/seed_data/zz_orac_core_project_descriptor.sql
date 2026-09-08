--liquibase formatted sql
-- Author: clive
-- Date: 31-Aug-2026
-- Description: Corrects the canonical ORAC_CORE authorised-domain descriptor.

--changeset clive:update_orac_core_project_descriptor_for_authorised_ai_material context:core labels:core stripComments:false
update orac_core.project_registry
   set description = 'Authorised Orac and artificial intelligence knowledge covering AI operating systems, intelligent agents, automation architecture, model governance, configuration, guardrails, operator procedures, and technical reference material.'
 where project_code = 'ORAC_CORE'
   and description = 'Canonical scope for Orac-wide architecture, configuration, guardrail, and operator documentation.';
--rollback update orac_core.project_registry set description = 'Canonical scope for Orac-wide architecture, configuration, guardrail, and operator documentation.' where project_code = 'ORAC_CORE' and description = 'Authorised Orac and artificial intelligence knowledge covering AI operating systems, intelligent agents, automation architecture, model governance, configuration, guardrails, operator procedures, and technical reference material.';
