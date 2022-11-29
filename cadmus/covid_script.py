#!/home/jcampbell/miniconda3/envs/dashenv/bin/python3.8
from cadmus import bioscraping
email = 's0565787@ed.ac.uk'
NCBI_API_KEY = 'eeb5b003283fba487503900053450dd7c507'
CROSSREF_API_KEY = '8f5ec160-9bea2c4f-55546a8b-787ac730'

query = '(COVID-19[Title] OR Sars-CoV-2[Title] OR Coronavirus[Title] OR severe acute respiratory syndrome coronavirus 2[Title]) AND (cohort[Title] OR retrospective[Title] OR prospective[Title] OR case series[Title] OR Multicenter Study[PT] OR Observational Study[PT] OR Comparative Study[PT] OR Case Reports[PT]) NOT (pregnan*[Title] OR breast[Title] or milk[Title] OR postpartum[Title]or child[TIAB] OR children[TIAB] OR pediatric*[TIAB] OR paediatric*[TIAB] OR adolescen*[TIAB] OR infan*[TIAB]) AND (English[LANG]) AND (2019/11/01:3000/01/01[Publication Date])'

print('starting bioscraping')
val = bioscraping(query, email, NCBI_API_KEY, CROSSREF_API_KEY)
print('bioscraping complete')
