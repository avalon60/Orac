--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.

--changeset clive:orac_chess_java_095_UnicodeUnpairedSurrogateRemover context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_source clob;
begin
  l_source := l_source || to_clob('create or replace java source named "org/apache/commons/lang3/text/translate/UnicodeUnpairedSurrogateRemover" as
/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.commons.lang3.text.translate;
import java.io.IOException;
import java.io.Writer;
/**
 * Helper subclass to CharSequenceTranslator to remove unpaired surrogates.
 *
 * @deprecated as of 3.6, use commons-text
 * <a href="https://commons.apache.org/proper/commons-text/javadocs/api-release/org/apache/commons/text/translate/UnicodeUnpairedSurrogateRemover.html">
 * UnicodeUnpairedSurrogateRemover</a> instead
 */
@Deprecated
public class UnicodeUnpairedSurrogateRemover extends CodePointTranslator {
    /**
     * Implementation of translate that throws out unpaired surrogates.
     * {@inheritDoc}
     */
    @Override
    public boolean translate(final int codepoint, final Writer out) throws IOException {
        // true: It''s a surrogate. Write nothing and say we''ve translated.
        return codepoint >= Character.MIN_SURROGATE && codepoint <= Character.MAX_SURROGATE;
        // It''s not a surrogate. Don''t translate it.
    }
}');
  execute immediate l_source;
end;
/
--rollback drop java source "org/apache/commons/lang3/text/translate/UnicodeUnpairedSurrogateRemover";
