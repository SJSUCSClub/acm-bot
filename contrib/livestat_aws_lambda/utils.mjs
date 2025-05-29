export function list2obj(list) {
  return Object.fromEntries(services.map(s => {
    const {id, ...rest} = s;
    return [id, rest];
  }));
}

export function dateStored2Locale(dateStr) {
  const date = new Date(dateStr);
  // Timezone is set by TZ environment variable, which will get picked up by NodeJS (and libc) automatically
  return date.toLocaleString("en-US", { timeZoneName: "shortOffset" });
}
