# This script is to set up edirect program on your computer
# We use edirect to avoid the 10000 document limit now imposed on the NCBI API. 
# This can all be found at https://www.ncbi.nlm.nih.gov/books/NBK179288/
def edirect_setup(ncbi_api_key)
  print('Checking for Edirect installation')
  # check if edirect is already installed
  check = ! esearch
  # you get a missing database parameter error if its already installed
  if check == [' ERROR:  Missing -db argument']:
    print('Edirect already installed)
    pass
  else:
    # download the edirect package and say yes at the prompt
    ! yes | sh -c "$(curl -fsSL ftp://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"
    # add the edirect path to the shell path variable 
    ! echo "export PATH=\$PATH:\$HOME/edirect" >> $HOME/.bash_profile
    # add the api key to the bash profile
    api_string = f'export NCBI_API_KEY={ncbi_api_key}'
    ! echo $api_string >>~/.bash_profile
    print('Edirect now installed')

