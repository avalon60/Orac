--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Seeds protected P2-03 reference data and reviewed metadata catalogues.

--changeset clive:seed_orac_core_p2_03_reference_domains context:core labels:core stripComments:false splitStatements:false endDelimiter:/
declare
  procedure seed_domain(
    p_domain_code in varchar2,
    p_display_name in varchar2,
    p_description in varchar2
  )
  is
  begin
    merge into orac_core.domain_codes dst
    using (
      select p_domain_code domain_code,
             p_display_name display_name,
             p_description description
        from dual
    ) src
       on (dst.domain_code = src.domain_code)
     when matched then update
          set dst.display_name = src.display_name,
              dst.description = src.description,
              dst.active_yn = 'Y',
              dst.system_required_yn = 'Y'
     when not matched then insert (
          domain_code, display_name, description, active_yn, system_required_yn
     ) values (
          src.domain_code, src.display_name, src.description, 'Y', 'Y'
     );
  end seed_domain;

  procedure seed_value(
    p_domain_code in varchar2,
    p_ref_value_code in varchar2,
    p_display_value in varchar2,
    p_display_sequence in number
  )
  is
  begin
    merge into orac_core.domain_ref_values dst
    using (
      select p_domain_code domain_code,
             p_ref_value_code ref_value_code,
             p_display_value display_value,
             p_display_sequence display_sequence
        from dual
    ) src
       on (dst.domain_code = src.domain_code
       and dst.ref_value_code = src.ref_value_code)
     when matched then update
          set dst.display_value = src.display_value,
              dst.description = src.display_value,
              dst.display_sequence = src.display_sequence,
              dst.active_yn = 'Y',
              dst.system_required_yn = 'Y'
     when not matched then insert (
          domain_code, ref_value_code, display_value, description,
          display_sequence, active_yn, system_required_yn
     ) values (
          src.domain_code, src.ref_value_code, src.display_value, src.display_value,
          src.display_sequence, 'Y', 'Y'
     );
  end seed_value;
begin
  seed_domain('CAPABILITY_CLASS', 'Capability Class', 'Provider-neutral capability classification.');
  seed_value('CAPABILITY_CLASS', 'PRIMARY_TEXT_REASONING', 'Primary Text Reasoning', 10);
  seed_value('CAPABILITY_CLASS', 'DETERMINISTIC_INSPECTION', 'Deterministic Inspection', 20);
  seed_value('CAPABILITY_CLASS', 'DETERMINISTIC_TRANSFORMATION', 'Deterministic Transformation', 30);
  seed_value('CAPABILITY_CLASS', 'DETERMINISTIC_CALCULATION', 'Deterministic Calculation', 40);
  seed_value('CAPABILITY_CLASS', 'SPECIALIST_INTERPRETATION', 'Specialist Interpretation', 50);
  seed_domain('CAPABILITY_EVIDENCE_STATE', 'Capability Evidence State', 'Maturity of dated provider or concrete-model evidence.');
  seed_value('CAPABILITY_EVIDENCE_STATE', 'UNASSESSED', 'Unassessed', 10);
  seed_value('CAPABILITY_EVIDENCE_STATE', 'API_DECLARED', 'API Declared', 20);
  seed_value('CAPABILITY_EVIDENCE_STATE', 'MODEL_METADATA_VERIFIED', 'Model Metadata Verified', 30);
  seed_value('CAPABILITY_EVIDENCE_STATE', 'BOUNDED_PROBE_VERIFIED', 'Bounded Probe Verified', 40);
  seed_value('CAPABILITY_EVIDENCE_STATE', 'REJECTED', 'Rejected', 50);
  seed_domain('CAPABILITY_LIFECYCLE', 'Capability Lifecycle', 'Planning lifecycle for capability definitions.');
  seed_value('CAPABILITY_LIFECYCLE', 'DEFINED', 'Defined', 10);
  seed_value('CAPABILITY_LIFECYCLE', 'DEFERRED', 'Deferred', 20);
  seed_value('CAPABILITY_LIFECYCLE', 'DEPRECATED', 'Deprecated', 30);
  seed_domain('PROVIDER_METADATA_STATUS', 'Provider Metadata Status', 'Review status of provider adapter metadata.');
  seed_value('PROVIDER_METADATA_STATUS', 'REVIEWED', 'Reviewed', 10);
  seed_value('PROVIDER_METADATA_STATUS', 'DEPRECATED', 'Deprecated', 20);
  seed_domain('PROCESSING_LOCALITY', 'Processing Locality', 'Where processing may occur.');
  seed_value('PROCESSING_LOCALITY', 'LOCAL', 'Local', 10);
  seed_value('PROCESSING_LOCALITY', 'REMOTE', 'Remote', 20);
  seed_value('PROCESSING_LOCALITY', 'HYBRID', 'Hybrid', 30);
  seed_value('PROCESSING_LOCALITY', 'UNKNOWN', 'Unknown', 40);
  seed_value('PROCESSING_LOCALITY', 'UNMAPPED', 'Unmapped', 50);
  seed_domain('ADAPTER_SUPPORT_STATUS', 'Adapter Support Status', 'Orac adapter implementation posture for a provider input.');
  seed_value('ADAPTER_SUPPORT_STATUS', 'IMPLEMENTED', 'Implemented', 10);
  seed_value('ADAPTER_SUPPORT_STATUS', 'NOT_IMPLEMENTED', 'Not Implemented', 20);
  seed_value('ADAPTER_SUPPORT_STATUS', 'REJECTED', 'Rejected', 30);
  seed_domain('MIME_MATCH_KIND', 'MIME Match Kind', 'Whether a controlled MIME value is exact or a type wildcard.');
  seed_value('MIME_MATCH_KIND', 'EXACT', 'Exact', 10);
  seed_value('MIME_MATCH_KIND', 'TYPE_WILDCARD', 'Type Wildcard', 20);
  seed_domain('LIMIT_DIMENSION', 'Limit Dimension', 'Dimension qualified by a bound operator, value, and unit.');
  seed_value('LIMIT_DIMENSION', 'BYTES', 'Bytes', 10);
  seed_value('LIMIT_DIMENSION', 'MEMBERS', 'Members', 20);
  seed_value('LIMIT_DIMENSION', 'EXPANDED_BYTES', 'Expanded Bytes', 30);
  seed_value('LIMIT_DIMENSION', 'PAGES', 'Pages', 40);
  seed_value('LIMIT_DIMENSION', 'OBJECTS', 'Objects', 50);
  seed_value('LIMIT_DIMENSION', 'PIXELS', 'Pixels', 60);
  seed_value('LIMIT_DIMENSION', 'CELLS', 'Cells', 70);
  seed_value('LIMIT_DIMENSION', 'DURATION', 'Duration', 80);
  seed_value('LIMIT_DIMENSION', 'CHANNELS', 'Channels', 90);
  seed_value('LIMIT_DIMENSION', 'FRAMES', 'Frames', 100);
  seed_value('LIMIT_DIMENSION', 'INPUT_TOKENS', 'Input Tokens', 110);
  seed_value('LIMIT_DIMENSION', 'OUTPUT_TOKENS', 'Output Tokens', 120);
  seed_value('LIMIT_DIMENSION', 'OUTPUT_BYTES', 'Output Bytes', 130);
  seed_value('LIMIT_DIMENSION', 'RETRIES', 'Retries', 140);
  seed_value('LIMIT_DIMENSION', 'ELAPSED_TIME', 'Elapsed Time', 150);
  seed_domain('LIMIT_UNIT', 'Limit Unit', 'Controlled units for provider and model input limits.');
  seed_value('LIMIT_UNIT', 'BYTE', 'Byte', 10);
  seed_value('LIMIT_UNIT', 'COUNT', 'Count', 20);
  seed_value('LIMIT_UNIT', 'PIXEL', 'Pixel', 30);
  seed_value('LIMIT_UNIT', 'CELL', 'Cell', 40);
  seed_value('LIMIT_UNIT', 'SECOND', 'Second', 50);
  seed_value('LIMIT_UNIT', 'MILLISECOND', 'Millisecond', 60);
  seed_value('LIMIT_UNIT', 'CHANNEL', 'Channel', 70);
  seed_value('LIMIT_UNIT', 'FRAME', 'Frame', 80);
  seed_value('LIMIT_UNIT', 'TOKEN', 'Token', 90);
  seed_value('LIMIT_UNIT', 'RETRY', 'Retry', 100);
  seed_domain('BOUND_OPERATOR', 'Bound Operator', 'Controlled numeric bound comparison operator.');
  seed_value('BOUND_OPERATOR', 'LE', 'Less Than Or Equal', 10);
  seed_value('BOUND_OPERATOR', 'LT', 'Less Than', 20);
  seed_value('BOUND_OPERATOR', 'EQ', 'Equal', 30);
  seed_value('BOUND_OPERATOR', 'GE', 'Greater Than Or Equal', 40);
  seed_value('BOUND_OPERATOR', 'GT', 'Greater Than', 50);
end;
/
--rollback update orac_core.domain_ref_values set active_yn = 'N' where domain_code in ('CAPABILITY_CLASS', 'CAPABILITY_EVIDENCE_STATE', 'CAPABILITY_LIFECYCLE', 'PROVIDER_METADATA_STATUS', 'PROCESSING_LOCALITY', 'ADAPTER_SUPPORT_STATUS', 'MIME_MATCH_KIND', 'LIMIT_DIMENSION', 'LIMIT_UNIT', 'BOUND_OPERATOR');
--rollback update orac_core.domain_codes set active_yn = 'N' where domain_code in ('CAPABILITY_CLASS', 'CAPABILITY_EVIDENCE_STATE', 'CAPABILITY_LIFECYCLE', 'PROVIDER_METADATA_STATUS', 'PROCESSING_LOCALITY', 'ADAPTER_SUPPORT_STATUS', 'MIME_MATCH_KIND', 'LIMIT_DIMENSION', 'LIMIT_UNIT', 'BOUND_OPERATOR');

--changeset clive:seed_orac_core_p2_03_metadata_catalogues context:core labels:core stripComments:false splitStatements:false endDelimiter:/
declare
  procedure seed_provider(
    p_provider_code in varchar2,
    p_display_name in varchar2,
    p_adapter_class in varchar2
  )
  is
  begin
    merge into orac_core.llm_providers dst
    using (
      select p_provider_code provider_code,
             p_display_name display_name,
             p_adapter_class adapter_class
        from dual
    ) src
       on (dst.provider_code = src.provider_code)
     when matched then update
          set dst.display_name = src.display_name,
              dst.adapter_class = src.adapter_class,
              dst.processing_locality_ref_value_code = 'LOCAL',
              dst.metadata_status_ref_value_code = 'REVIEWED',
              dst.effective_to = null
     when not matched then insert (
          provider_code, display_name, adapter_class,
          processing_locality_ref_value_code,
          metadata_status_ref_value_code
     ) values (
          src.provider_code, src.display_name, src.adapter_class,
          'LOCAL', 'REVIEWED'
     );
  end seed_provider;

  procedure seed_capability(
    p_capability_code in varchar2,
    p_display_name in varchar2,
    p_class_code in varchar2,
    p_lifecycle_code in varchar2,
    p_behaviour_summary in varchar2
  )
  is
  begin
    merge into orac_core.llm_capabilities dst
    using (
      select p_capability_code capability_code,
             p_display_name display_name,
             p_class_code class_code,
             p_lifecycle_code lifecycle_code,
             p_behaviour_summary behaviour_summary
        from dual
    ) src
       on (dst.capability_code = src.capability_code)
     when matched then update
          set dst.display_name = src.display_name,
              dst.capability_class_ref_value_code = src.class_code,
              dst.capability_lifecycle_ref_value_code = src.lifecycle_code,
              dst.behaviour_summary = src.behaviour_summary
     when not matched then insert (
          capability_code, display_name,
          capability_class_ref_value_code,
          capability_lifecycle_ref_value_code,
          behaviour_summary
     ) values (
          src.capability_code, src.display_name,
          src.class_code, src.lifecycle_code, src.behaviour_summary
     );
  end seed_capability;

  procedure seed_representation(
    p_representation_code in varchar2,
    p_display_name in varchar2,
    p_description in varchar2
  )
  is
  begin
    merge into orac_core.llm_input_representations dst
    using (
      select p_representation_code representation_code,
             p_display_name display_name,
             p_description description
        from dual
    ) src
       on (dst.representation_code = src.representation_code)
     when matched then update
          set dst.display_name = src.display_name,
              dst.description = src.description
     when not matched then insert (
          representation_code, display_name, description
     ) values (
          src.representation_code, src.display_name, src.description
     );
  end seed_representation;

  procedure seed_media_type(
    p_media_type in varchar2,
    p_display_name in varchar2,
    p_match_kind in varchar2
  )
  is
  begin
    merge into orac_core.llm_input_media_types dst
    using (
      select p_media_type media_type,
             p_display_name display_name,
             p_match_kind match_kind
        from dual
    ) src
       on (dst.media_type = src.media_type)
     when matched then update
          set dst.display_name = src.display_name,
              dst.mime_match_kind_ref_value_code = src.match_kind,
              dst.description = src.display_name
     when not matched then insert (
          media_type, display_name,
          mime_match_kind_ref_value_code, description
     ) values (
          src.media_type, src.display_name,
          src.match_kind, src.display_name
     );
  end seed_media_type;

  procedure seed_provider_input(
    p_provider_code in varchar2,
    p_representation_code in varchar2,
    p_media_type in varchar2,
    p_adapter_status in varchar2,
    p_source_uri in varchar2
  )
  is
  begin
    merge into orac_core.llm_provider_inputs dst
    using (
      select p_provider_code provider_code,
             p_representation_code representation_code,
             p_media_type media_type,
             p_adapter_status adapter_status,
             p_source_uri source_uri
        from dual
    ) src
       on (dst.provider_code = src.provider_code
       and dst.representation_code = src.representation_code
       and nvl(dst.media_type, '~') = nvl(src.media_type, '~'))
     when matched then update
          set dst.evidence_state_ref_value_code = 'API_DECLARED',
              dst.adapter_status_ref_value_code = src.adapter_status,
              dst.source_uri = src.source_uri,
              dst.checked_on = timestamp '2026-08-22 00:00:00',
              dst.effective_to = null,
              dst.reviewed_by = 'clive',
              dst.provenance = 'P2-03 reviewed provider documentation',
              dst.rejection_reason = null
     when not matched then insert (
          provider_code, representation_code, media_type,
          evidence_state_ref_value_code, adapter_status_ref_value_code,
          source_uri, checked_on, reviewed_by, provenance
     ) values (
          src.provider_code, src.representation_code, src.media_type,
          'API_DECLARED', src.adapter_status,
          src.source_uri, timestamp '2026-08-22 00:00:00',
          'clive', 'P2-03 reviewed provider documentation'
     );
  end seed_provider_input;
begin
  seed_provider('ollama', 'Ollama', 'model.llm_connector.OllamaConnector');
  seed_provider('lmstudio', 'LM Studio', 'model.llm_connector.LMStudioConnector');

  seed_capability('text_reasoning', 'Primary text reasoning', 'PRIMARY_TEXT_REASONING', 'DEFINED', 'Produce a bounded text response from authorised structured evidence.');
  seed_capability('container_inspection', 'Container inspection', 'DETERMINISTIC_INSPECTION', 'DEFINED', 'Verify signature, structure, member inventory, encryption, active content, and expansion risk.');
  seed_capability('bounded_media_selection', 'Bounded media selection', 'DETERMINISTIC_INSPECTION', 'DEFINED', 'Resolve an authorised policy-bounded media subset for downstream processing.');
  seed_capability('layout_extraction', 'Document layout extraction', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Extract ordered text blocks, objects, geometry, and reading-order candidates.');
  seed_capability('page_rendering', 'Bounded page rendering', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Render selected document pages or regions under a fixed raster profile.');
  seed_capability('ocr_text_extraction', 'OCR text extraction', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Recognise text from bounded raster evidence with coordinates and uncertainty.');
  seed_capability('document_visual_interpretation', 'Document visual interpretation', 'SPECIALIST_INTERPRETATION', 'DEFINED', 'Explain selected document visual relationships using attributed evidence.');
  seed_capability('technical_image_interpretation', 'Technical image interpretation', 'SPECIALIST_INTERPRETATION', 'DEFINED', 'Explain topology, labels, and spatial meaning in selected technical images.');
  seed_capability('chart_visual_interpretation', 'Chart visual interpretation', 'SPECIALIST_INTERPRETATION', 'DEFINED', 'Explain chart encodings while grounding numeric claims in deterministic data.');
  seed_capability('workbook_structured_extraction', 'Workbook structured extraction', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Extract workbook structure, cells, formulas, charts, and metadata deterministically.');
  seed_capability('spreadsheet_calculation', 'Deterministic spreadsheet calculation', 'DETERMINISTIC_CALCULATION', 'DEFINED', 'Calculate spreadsheet results with an approved deterministic engine.');
  seed_capability('sheet_chart_rendering', 'Sheet and chart rendering', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Render bounded sheets, ranges, dashboards, or charts under a fixed profile.');
  seed_capability('presentation_structured_extraction', 'Presentation structured extraction', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Extract slide objects, text, notes, relationships, and metadata deterministically.');
  seed_capability('slide_rendering', 'Bounded slide rendering', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Render selected slides or regions under a fixed profile.');
  seed_capability('presentation_visual_interpretation', 'Presentation visual interpretation', 'SPECIALIST_INTERPRETATION', 'DEFINED', 'Explain selected presentation composition using attributed evidence.');
  seed_capability('audio_metadata_inspection', 'Audio metadata inspection', 'DETERMINISTIC_INSPECTION', 'DEFINED', 'Inspect codec, duration, channels, tracks, and container metadata.');
  seed_capability('speech_transcription', 'Speech transcription', 'SPECIALIST_INTERPRETATION', 'DEFINED', 'Transcribe bounded speech selections with timestamps and uncertainty.');
  seed_capability('speaker_diarisation', 'Speaker diarisation', 'SPECIALIST_INTERPRETATION', 'DEFINED', 'Separate bounded speech into attributed speaker-change segments without identity claims.');
  seed_capability('audio_semantic_interpretation', 'Audio semantic interpretation', 'SPECIALIST_INTERPRETATION', 'DEFINED', 'Describe bounded non-speech or prosodic evidence with attribution.');
  seed_capability('video_metadata_inspection', 'Video metadata inspection', 'DETERMINISTIC_INSPECTION', 'DEFINED', 'Inspect video container, streams, duration, frame, track, and subtitle metadata.');
  seed_capability('subtitle_extraction', 'Subtitle extraction', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Extract authoritative bounded subtitle evidence with timing.');
  seed_capability('keyframe_extraction', 'Keyframe extraction', 'DETERMINISTIC_TRANSFORMATION', 'DEFINED', 'Extract bounded deterministic video frames under a declared sampling profile.');
  seed_capability('video_temporal_interpretation', 'Video temporal interpretation', 'SPECIALIST_INTERPRETATION', 'DEFERRED', 'Interpret temporal relationships across a bounded video selection.');

  seed_representation('normalised_text_evidence', 'Normalised text evidence', 'Controlled P2-03 evidence representation.');
  seed_representation('verified_source_container', 'Verified source container', 'Controlled P2-03 evidence representation.');
  seed_representation('verified_source_media', 'Verified source media', 'Controlled P2-03 evidence representation.');
  seed_representation('inspection_metadata', 'Inspection metadata', 'Controlled P2-03 evidence representation.');
  seed_representation('bounded_selection_manifest', 'Bounded selection manifest', 'Controlled P2-03 evidence representation.');
  seed_representation('structured_derivative', 'Structured derivative', 'Controlled P2-03 evidence representation.');
  seed_representation('raster_image_derivative', 'Raster image derivative', 'Controlled P2-03 evidence representation.');
  seed_representation('sheet_chart_render', 'Sheet or chart render', 'Controlled P2-03 evidence representation.');
  seed_representation('slide_render', 'Slide render', 'Controlled P2-03 evidence representation.');
  seed_representation('decoded_audio_selection', 'Decoded audio selection', 'Controlled P2-03 evidence representation.');
  seed_representation('time_aligned_text', 'Time-aligned text', 'Controlled P2-03 evidence representation.');
  seed_representation('video_frame_selection', 'Video frame selection', 'Controlled P2-03 evidence representation.');
  seed_representation('video_clip_selection', 'Video clip selection', 'Controlled P2-03 evidence representation.');

  seed_media_type('image/jpeg', 'JPEG image', 'EXACT');
  seed_media_type('image/png', 'PNG image', 'EXACT');
  seed_media_type('image/webp', 'WebP image', 'EXACT');

  seed_provider_input(
    'ollama',
    'normalised_text_evidence',
    null,
    'IMPLEMENTED',
    'https://docs.ollama.com/api/chat'
  );
  seed_provider_input(
    'lmstudio',
    'normalised_text_evidence',
    null,
    'IMPLEMENTED',
    'https://lmstudio.ai/docs/developer/openai-compat/chat-completions'
  );
  seed_provider_input(
    'ollama',
    'raster_image_derivative',
    null,
    'NOT_IMPLEMENTED',
    'https://docs.ollama.com/capabilities/vision'
  );
  seed_provider_input(
    'lmstudio',
    'raster_image_derivative',
    'image/jpeg',
    'NOT_IMPLEMENTED',
    'https://lmstudio.ai/docs/developer/core/image-input'
  );
  seed_provider_input(
    'lmstudio',
    'raster_image_derivative',
    'image/png',
    'NOT_IMPLEMENTED',
    'https://lmstudio.ai/docs/developer/core/image-input'
  );
  seed_provider_input(
    'lmstudio',
    'raster_image_derivative',
    'image/webp',
    'NOT_IMPLEMENTED',
    'https://lmstudio.ai/docs/developer/core/image-input'
  );
end;
/
--rollback delete from orac_core.llm_provider_inputs where provenance = 'P2-03 reviewed provider documentation';
--rollback delete from orac_core.llm_input_media_types where media_type in ('image/jpeg', 'image/png', 'image/webp');
--rollback delete from orac_core.llm_input_representations where representation_code in ('normalised_text_evidence', 'verified_source_container', 'verified_source_media', 'inspection_metadata', 'bounded_selection_manifest', 'structured_derivative', 'raster_image_derivative', 'sheet_chart_render', 'slide_render', 'decoded_audio_selection', 'time_aligned_text', 'video_frame_selection', 'video_clip_selection');
--rollback delete from orac_core.llm_capabilities where capability_code in ('text_reasoning', 'container_inspection', 'bounded_media_selection', 'layout_extraction', 'page_rendering', 'ocr_text_extraction', 'document_visual_interpretation', 'technical_image_interpretation', 'chart_visual_interpretation', 'workbook_structured_extraction', 'spreadsheet_calculation', 'sheet_chart_rendering', 'presentation_structured_extraction', 'slide_rendering', 'presentation_visual_interpretation', 'audio_metadata_inspection', 'speech_transcription', 'speaker_diarisation', 'audio_semantic_interpretation', 'video_metadata_inspection', 'subtitle_extraction', 'keyframe_extraction', 'video_temporal_interpretation');
--rollback delete from orac_core.llm_providers where provider_code in ('ollama', 'lmstudio');

