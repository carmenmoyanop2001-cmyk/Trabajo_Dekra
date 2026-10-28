using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;
using System.Text.Json;
foreach (string path in args) {
 try {
 using var doc = SpreadsheetDocument.Open(path, false);
 var validator = new OpenXmlValidator(FileFormatVersions.Office2021) { MaxNumberOfErrors = 80 };
 var errors = validator.Validate(doc).Select(e => new { e.Id, e.Description, Part=e.Part?.Uri.ToString(), Path=e.Path?.XPath }).ToList();
 Console.WriteLine(JsonSerializer.Serialize(new { File=path, Count=errors.Count, Errors=errors }));
 if (errors.Count > 0) Environment.ExitCode = 1;
 } catch(Exception e) { Environment.ExitCode = 1; Console.WriteLine(JsonSerializer.Serialize(new { File=path, Exception=e.ToString() })); }
}
