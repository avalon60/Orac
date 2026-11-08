--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.

--changeset clive:orac_chess_java_035_MoveException context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_source clob;
begin
  l_source := l_source || to_clob('create or replace java source named "com/github/bhlangonijr/chesslib/move/MoveException" as
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
package com.github.bhlangonijr.chesslib.move;
/**
 * Thrown to indicate a failure executing a move, for instance because the move is considered illegal in the context of
 * the game it is played.
 */
public class MoveException extends RuntimeException {
    private static final long serialVersionUID = 6523240383760826752L;
    /**
     * Constructs a new move exception.
     */
    public MoveException() {
        super();
    }
    /**
     * Constructs a new move exception with the specified detail message and cause.
     *
     * @param message the error message
     * @param cause   the cause
     */
    public MoveException(String message, Throwable cause) {
        super(message, cause);
    }
    /**
     * Constructs a new move exception with the specified detail message.
     *
     * @param message the error message
     */
    public MoveException(String message) {
        super(message);
    }
    /**
     * Constructs a new move exception with the specified cause.
     *
     * @param cause the cause
     */
    public MoveException(Throwable cause) {
        super(cause);
    }
}');
  execute immediate l_source;
end;
/
--rollback drop java source "com/github/bhlangonijr/chesslib/move/MoveException";
