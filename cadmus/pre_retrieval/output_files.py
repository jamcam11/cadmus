import os

def output_files ():
    #creating the directories we are planning on using to save the results of the retrieval system
    for path in ['output',
                'output/retrieved_df',
                'output/esearch_results',
                'output/medline',
                'output/medline/txts',
                'output/crossref',
                'output/formats',
                'output/formats/xmls',
                'output/formats/pdfs',
                'output/formats/htmls',
                'output/formats/txts',
                'output/formats/zips',
                'output/formats/tgzs'
                'output/formats/xmls/parsed',
                'output/formats/pdfs/parsed',
                'output/formats/htmls/parsed',
                'output/formats/txts/parsed',
                'output/formats/zips/parsed',
                'output/formats/tgzs/parsed']:
        try:
            #try to create the directory, most likely will work for new project
            os.mkdir(path)
            print(f'Now creating {path}')
        except:
            #if the directory already exist just pass
            pass