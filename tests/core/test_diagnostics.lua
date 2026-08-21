return function(T)
  local Diagnostics = T.loadCore("Diagnostics")

  T.test("stores structured entries in bounded order", function()
    local now = 10
    local diagnostics = Diagnostics.new({ capacity = 2, burst = 10,
      clock = function() return now end })
    diagnostics:info("CORE.FIRST", "one", { map = "PALLET", nested = {} })
    now = 11
    diagnostics:warn("CORE.SECOND", "two")
    now = 12
    diagnostics:error("CORE.THIRD", "three")
    local rows = diagnostics:snapshot()
    T.equal(#rows, 2)
    T.equal(rows[1].code, "CORE.SECOND")
    T.equal(rows[2].code, "CORE.THIRD")
    T.equal(rows[2].sequence, 3)
    T.equal(diagnostics:snapshot("error")[1].message, "three")
  end)

  T.test("rate limits per code and reports suppressed count", function()
    local now = 0
    local diagnostics = Diagnostics.new({ capacity = 8, rate = 1, burst = 2,
      clock = function() return now end })
    T.truthy(diagnostics:warn("CORE.REPEAT", "first"))
    T.truthy(diagnostics:warn("CORE.REPEAT", "second"))
    local row, reason = diagnostics:warn("CORE.REPEAT", "third")
    T.equal(row, nil)
    T.equal(reason, "rate_limited")
    now = 1
    row = diagnostics:warn("CORE.REPEAT", "fourth")
    T.equal(row.suppressed, 1)
    T.equal(diagnostics:stats().suppressed, 1)
  end)

  T.test("force bypasses rate limiting and sink errors are isolated", function()
    local diagnostics = Diagnostics.new({ rate = 0, burst = 1,
      clock = function() return 0 end,
      sink = function() error("sink broke") end })
    diagnostics:info("CORE.FORCED", "one")
    local forced = diagnostics:info("CORE.FORCED", "two", nil, { force = true })
    T.truthy(forced)
    T.equal(diagnostics:stats().sinkErrors, 2)
  end)

  T.test("rejects malformed diagnostic vocabulary", function()
    local diagnostics = Diagnostics.new({ clock = function() return 0 end })
    T.raises(function() diagnostics:emit("fatal", "CORE.BAD", "bad") end,
      "unknown diagnostic level")
    T.raises(function() diagnostics:info("free form", "bad") end,
      "invalid diagnostic code")
  end)

  T.test("bounds payloads and isolates retained entries from consumers", function()
    local sinkRow
    local diagnostics = Diagnostics.new({ capacity = 2, burst = 2,
      maxMessageBytes = 8, maxFieldBytes = 5, maxFields = 2,
      clock = function() return 0 end,
      sink = function(row)
        sinkRow = row
        row.message = "sink mutation"
        row.fields.first = "sink mutation"
      end })
    local returned = diagnostics:info("CORE.BOUNDED", "message-too-long", {
      first = "abcdef", second = true, third = "omitted",
    })
    returned.message = "caller mutation"
    returned.fields.first = "caller mutation"

    local retained = diagnostics:snapshot()[1]
    T.equal(#retained.message, 8)
    T.truthy(retained.messageTruncated)
    T.truthy(retained.fieldsTruncated)
    T.truthy(retained.message ~= sinkRow.message)
    T.truthy(retained.fields.first ~= "sink mutation")
    T.truthy(retained.fields.first ~= "caller mutation")

    retained.message = "snapshot mutation"
    T.truthy(diagnostics:snapshot()[1].message ~= "snapshot mutation")
  end)
end
