from cadmus.src.parsing import clean_soup
from cadmus.src.parsing import html_get_ab
from cadmus.src.parsing.html_to_parsed_text import html_to_parsed_text
from cadmus.src.evaluation.abstract_similarity_score import abstract_similarity_score
from cadmus.src.evaluation.body_unique_score import body_unique_score
from cadmus.src.retrieval import redirect_check
import bs4
from bs4 import BeautifulSoup

def html_response_to_parse_d(retrieval_df, index, response):
    parse_d = {}
    # read the file in as a soup object
    abstract = ''
    soup = BeautifulSoup(response.text, 'html')
    
    if retrieval_df.loc[index, 'abstract'] != '' and retrieval_df.loc[index, 'abstract'] != None and retrieval_df.loc[index, 'abstract'] == retrieval_df.loc[index, 'abstract']:
        abstract = retrieval_df.loc[index, 'abstract']
    
    # our requests strategy has a major issue with java script redirection.
    # This means a lot of pages are redirection pages and need to be ignored.
    redirect = redirect_check(soup)
    
    if redirect == True:
        
        text = ''
        size = 0
        wc = 0
        eval
    
    else:
        # clean out the unwanted tags ('a' and 'script')    
        soup = clean_soup(soup)
        
        if retrieval_df.loc[index, 'abstract'] == '' or retrieval_df.loc[index, 'abstract'] == None or retrieval_df.loc[index, 'abstract'] != retrieval_df.loc[index, 'abstract']:
            #parse abstract using function above
            abstract = html_get_ab(soup)
       
        # parse out the body text 
        text = html_to_parsed_text(soup)
        
        # get the file_size
        size = len(response.content)
        
        # get the word_count
        if text:
            wc = len(text.split())
        else:
            wc = 0       

    bu_score = body_unique_score(text, abstract)
    as_score = abstract_similarity_score(text, abstract)
    
    # now lets update our df with the new variable we have parsed/made
    parse_d.update({'file_path':f'./output/formats/htmls/{index}.html',
                    'text':text,
                    'abstract':abstract,
                    'size':size,
                    'wc':wc,
                    'url':response.url,
                    'body_unique_score':bu_score,
                    'ab_sim_score':as_score})
    if retrieval_df.loc[index, 'abstract'] == '' or retrieval_df.loc[index, 'abstract'] == None or retrieval_df.loc[index, 'abstract'] != retrieval_df.loc[index, 'abstract']:
        retrieval_df.loc[index, 'abstract'] = abstract
    else:
        pass
    
    return parse_d