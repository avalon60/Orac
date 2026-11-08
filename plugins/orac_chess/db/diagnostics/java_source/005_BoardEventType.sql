--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.

--changeset clive:orac_chess_java_005_BoardEventType context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_source clob;
begin
  l_source := l_source || to_clob('create or replace java source named "com/github/bhlangonijr/chesslib/BoardEventType" as
/*
 * Copyright 2017 Ben-Hur Carlos Vieira Langoni Junior
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.github.bhlangonijr.chesslib;
/**
 * All possible types of a {@link BoardEvent}.
 */
public enum BoardEventType {
    /**
     * The type for an event emitted when a move is played on the board.
     */
    ON_MOVE,
    /**
     * The type for an event emitted when a move is reverted on the board.
     */
    ON_UNDO_MOVE,
    /**
     * The type for an event emitted when a board is loaded.
     */
    ON_LOAD;
    /**
     * Returns a board event type given its name.
     * <p>
     * Same as invoking {@link BoardEventType#valueOf(String)}.
     *
     * @param v name of the board event type
     * @return the board event type with the specified name
     * @throws IllegalArgumentException if the name does not correspond to any board event type
     */
    public static BoardEventType fromValue(String v) {
        return valueOf(v);
    }
    /**
     * Returns the name of the board event type.
     *
     * @return the name of the board event type
     */
    public String value() {
        return name();
    }
}');
  execute immediate l_source;
end;
/
--rollback drop java source "com/github/bhlangonijr/chesslib/BoardEventType";
