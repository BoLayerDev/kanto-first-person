return function(T)
  local Policy = assert(loadfile(T.root .. "/tools/ManifestPolicy.lua"))()

  T.test("manifest policy decodes the project manifest", function()
    local ok, err = Policy.validate(T.read("manifest.json"))
    T.truthy(ok)
    T.falsy(err)
  end)

  T.test("strict JSON rejects duplicate and escaped duplicate keys", function()
    local value, err = Policy.decode('{"key":1,"key":2}')
    T.falsy(value)
    T.truthy(err:find("duplicate JSON key", 1, true))

    value, err = Policy.decode('{"id":1,"\\u0069d":2}')
    T.falsy(value)
    T.truthy(err:find("duplicate JSON key", 1, true))

    value, err = Policy.decode('{"outer":{"key":1,"key":2}}')
    T.falsy(value)
    T.truthy(err:find("duplicate JSON key", 1, true))
  end)

  T.test("manifest policy reads fields from the root object only", function()
    local body = [[{
      "id":"ds_fp_ceiling",
      "api":2,
      "profile":"overhaul",
      "permissions":["filesystem"],
      "affects_link":true,
      "description":"decoy: \"permissions\": []"
    }]]
    local ok, err = Policy.validate(body)
    T.falsy(ok)
    T.equal(err, "manifest permissions must stay empty")
  end)
end
