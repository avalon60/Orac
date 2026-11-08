--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.

--changeset clive:orac_chess_java_028_Round context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_source clob;
begin
  l_source := l_source || to_clob('create or replace java source named "com/github/bhlangonijr/chesslib/game/Round" as
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
package com.github.bhlangonijr.chesslib.game;
import java.util.ArrayList;
import java.util.List;
/**
 * A round of a chess event.
 */
public class Round {
    private final List<Game> game = new ArrayList<>();
    private final Event event;
    private int number;
    /**
     * Constructs a new event round.
     *
     * @param event the event the round belongs to
     */
    public Round(Event event) {
        this.event = event;
    }
    /**
     * Returns the number of the round.
     *
     * @return the number of the round
     */
    public int getNumber() {
        return number;
    }
    /**
     * Sets the number of the round.
     *
     * @param number the number of the round
     */
    public void setNumber(int number) {
        this.number = number;
    }
    /**
     * Returns the list of games scheduled in the round.
     *
     * @return the games of the round
     */
    public List<Game> getGame() {
        return game;
    }
    /**
     * Returns the chess event the round refers to.
     *
     * @return the event the round belongs to
     */
    public Event getEvent() {
        return event;
    }
}');
  execute immediate l_source;
end;
/
--rollback drop java source "com/github/bhlangonijr/chesslib/game/Round";
